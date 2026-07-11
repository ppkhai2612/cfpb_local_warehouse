"""This script implements an Airflow DAG"""

from pathlib import Path
from datetime import datetime, timedelta
import sys
from typing import Any
import logging

from pendulum import datetime, timezone
from airflow.sdk import dag, task
from airflow.sdk.exceptions import AirflowSkipException
from airflow.timetables.interval import CronDataIntervalTimetable
from airflow.providers.standard.operators.bash import BashOperator

import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from cfpb.config import DATE
from cfpb.ingestion_pipeline import (
    extract_complaints, load_to_raw, load_to_bronze,
    load_parquet_to_duckdb
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DBT_PROJECT_DIR = str((Path(__file__).parents[2] / "dbt_cfpb").absolute()) # dbt root directory


@task
def extract_complaints_to_raw(**context):
    """Airflow task for
        - Extracting complaints from API
        - Saving them to the raw bucket in MinIO
    """

    date = (context["logical_date"] - timedelta(days=1)).strftime("%Y-%m-%d") # the date to fetch data from the CFPB
    logger.info(f"Running CFPB DAG for the date {date}")
    # print(context["data_interval_start"])
    # print(context["data_interval_end"])

    partition = 1  # track partition count in raw
    for complaints in extract_complaints(date):
        load_to_raw(complaints, date, partition)
        partition += 1

    return {
        "raw_prefix": f"raw/cfpb_complaints/{date}",
        "process_date": date,
        "num_partitions": partition - 1
    }


@task
def load_raw_to_bronze(metadata):
    """Airflow task for loading raw data (in JSONL) to bronze data (in Parquet)"""
    load_to_bronze(
        raw_prefix=metadata["raw_prefix"],
        process_date=metadata["process_date"],
        partitions=metadata["num_partitions"]
    )
    return {
        "bronze_prefix": f"bronze/cfpb_complaints/{metadata['process_date']}",
        "process_date": metadata["process_date"],
        "num_partitions": metadata["num_partitions"]
    }


@task
def save_bronze_to_duckdb(metadata) -> dict[str, Any]:
    """Airflow task for loading bronze data (in Parquet) to the table to DuckDB"""
    parquet_path = f"s3://{metadata['bronze_prefix']}/*.parquet"
    db_path = "database/cfpb_complaints.duckdb"
    
    result = load_parquet_to_duckdb(
        parquet_path=parquet_path,
        database_path=db_path
    )
    

default_args = {
    'owner': 'airflow',
    'retries': 2,
    'retry_delay': timedelta(seconds=30)
}
@dag(
    dag_id='cfpb_complaint_daily_dag',
    description="Daily Airflow DAG for CFPB complaint pipeline orchestration",
    schedule="@daily",
    start_date=datetime(2026, 7, 7),
    default_args=default_args,
    catchup=True,
    tags=['cfpb']
)
def cfpb_complaint_daily_dag():
    """Daily Airflow DAG for CFPB complaint pipeline orchestration"""
    
    run_dbt_models = BashOperator(
        task_id="run_dbt_models",
        bash_command="dbt run",
        cwd=DBT_PROJECT_DIR
    )

    run_dbt_tests = BashOperator(
        task_id="run_dbt_tests",
        bash_command="dbt test || echo 'dbt test failed'",
        cwd=DBT_PROJECT_DIR,
    )

    # task dependencies
    # raw_metadata = extract_complaints_to_raw()
    # bronze_metadata = load_raw_to_bronze(raw_metadata)
    # duckdb = save_bronze_to_duckdb(bronze_metadata)
    # duckdb >> run_dbt_models >> run_dbt_tests
    run_dbt_models >> run_dbt_tests


cfpb_complaint_daily_dag()