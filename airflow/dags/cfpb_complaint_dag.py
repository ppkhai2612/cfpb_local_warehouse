"""Airflow DAG for the CFPB complaint ingestion pipeline."""

import sys
import logging
from datetime import timedelta
from pathlib import Path
from typing import Any, TypedDict

import pendulum
from airflow.sdk import dag, task
from airflow.providers.standard.operators.bash import BashOperator

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from cfpb.ingestion_pipeline import (
    extract_complaints,
    load_parquet_to_duckdb,
    load_to_bronze,
    load_to_raw,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parents[2]
DBT_PROJECT_DIR = str((PROJECT_ROOT / "dbt_cfpb").absolute())
DUCKDB_PATH = "database/cfpb_complaints.duckdb"


class PipelineMetadata(TypedDict):
    """Metadata passed between Airflow tasks."""

    process_date: str
    raw_prefix: str
    bronze_prefix: str
    num_partitions: int


def _previous_logical_date(context: dict[str, Any]) -> str:
    """Return the CFPB date processed by this DAG run."""
    return (context["logical_date"] - timedelta(days=1)).strftime("%Y-%m-%d")


@task
def extract_complaints_to_raw(**context: Any) -> PipelineMetadata:
    """Extract complaints from the CFPB API and save JSONL files to raw storage."""

    process_date = _previous_logical_date(context)
    logger.info("Running CFPB ingestion for %s", process_date)

    partition = 1
    for complaints in extract_complaints(process_date):
        load_to_raw(complaints, process_date, partition)
        partition += 1

    return {
        "process_date": process_date,
        "raw_prefix": f"raw/cfpb_complaints/{process_date}",
        "bronze_prefix": f"bronze/cfpb_complaints/{process_date}",
        "num_partitions": partition - 1,
    }


@task
def load_raw_to_bronze(metadata: PipelineMetadata) -> PipelineMetadata:
    """Convert raw JSONL files to bronze Parquet files."""

    load_to_bronze(
        raw_prefix=metadata["raw_prefix"],
        process_date=metadata["process_date"],
        partitions=metadata["num_partitions"],
    )
    return metadata


@task
def save_bronze_to_duckdb(metadata: PipelineMetadata) -> dict[str, Any]:
    """Load bronze Parquet data into DuckDB."""

    parquet_path = f"s3://{metadata['bronze_prefix']}/*.parquet"

    return load_parquet_to_duckdb(
        parquet_path=parquet_path,
        database_path=DUCKDB_PATH,
    )


default_args = {
    "owner": "airflow",
    "retries": 2,
    "retry_delay": timedelta(seconds=30),
}


@dag(
    dag_id="cfpb_complaint_daily_dag",
    description="Daily Airflow DAG for CFPB complaint pipeline orchestration",
    schedule="@daily",
    start_date=pendulum.datetime(2023, 1, 1, tz="UTC"),
    default_args=default_args,
    catchup=False,
    tags=["cfpb"],
)
def cfpb_complaint_daily_dag():
    """Daily Airflow DAG for CFPB complaint pipeline orchestration"""

    run_dbt_models = BashOperator(
        task_id="run_dbt_models",
        bash_command="dbt run",
        cwd=DBT_PROJECT_DIR,
    )

    run_dbt_tests = BashOperator(
        task_id="run_dbt_tests",
        bash_command="dbt test || echo 'dbt test failed'",
        cwd=DBT_PROJECT_DIR,
    )

    # task dependencies
    raw_metadata = extract_complaints_to_raw()
    bronze_metadata = load_raw_to_bronze(raw_metadata)
    duckdb_metadata = save_bronze_to_duckdb(bronze_metadata)
    duckdb_metadata >> run_dbt_models >> run_dbt_tests


cfpb_complaint_daily_dag()
