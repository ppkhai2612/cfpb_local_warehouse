"""This script implements an Airflow DAG"""

from pathlib import Path
from datetime import datetime
import sys
from typing import Any
import logging

from airflow.sdk import dag, task
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from cfpb.config import START_DATE, COMPANIES
from cfpb.ingestion_pipeline import extract_complaints, save_parquet_to_bronze
import cfpb.scripts.minio_to_duckdb


logger = logging.getLogger(__name__)


@task(task_id="extract_complaint_to_landing")
def extract_complaint_to_landing(
    min_date: str,
    max_date: str,
    company_name: str
) -> str | None:
    """Airflow task for extracting complaints and saving them to the landing area
    Raw data stored in the landing area is in Parquet format
    
    Params:
        min_date: The minimum date for complaints to extract (YYYY-MM-DD)
        max_date: The maximum date for complaints to extract (YYYY-MM-DD)
        company_name: The name of the company to extract complaints for

    Returns:
        The path to the Parquet file saved in the landing area, or None if no complaints
    """
    logger.info(f"Extracting complaints for company named {company_name} from {min_date} to {max_date}")
    parquet_path = save_parquet_to_landing(
        date_received_min=min_date,
        date_received_min=max_date,
        company_name=company_name
    )
    return parquet_path


@task(task_id="load_landing_to_duckdb")
def load_landing_to_duckdb(
    parquet_path: str,
    database_path: str
) -> dict[str, Any]:
    """Airflow task for loading data from the landing area to DuckDB
    
    Params:
        parquet_path: The path to the Parquet file to load
        database_path: The path to the DuckDB database file
    
    Returns:
        A dictionary with information about the load result, such as number of rows loaded, time taken
    """
    logger.info(f"Loading Parquet file at {parquet_path} into DuckDB")
    result = load_parquet_to_duckdb(
        parquet_path=parquet_path,
        database_path=database_path
    )
    logger.info(f"COMPLETED: Loading Parquet file at {parquet_path} into DuckDB")
    return {
        "status": "success",
        "parquet_path": parquet_path,
        **result,
    }


@task()
def run_dbt_models():
    pass


@task()
def run_dbt_tests():
    pass


default_args = {
    'owner': 'airflow',
    'retries': 2,
    'retry_delay': timedelta(seconds=30)
}
@dag(
    dag_id='cfpb_complaint_daily_dag',
    description='DAG is run daily to extract complaint data, load it into',
    schedule='@daily',
    start_date=datetime(2023, 1, 1),
    default_args=default_args,
    catchup=False,
    tags=['cfpb']
)
def cfpb_complaint_daily_dag(
    database_path: str = "database/cfpb_complaints.duckdb"
) -> dict[str, Any]:
    """Daily Airflow DAG for CFPB complaint pipeline orchestration

    Tasks in the DAG:
        1. Extract complaints from CFPB API and load them into landing area (Parquet files)
        2. Load raw data into DuckDB
        3. Run dbt models to transform data
        4. Run dbt tests to serve data quality checks
        5. Generate analytics report/dashboard
    """

    logger.info(f"Starting CFPB Complaint Daily DAG")
    
    # Determine the date range for this run
    min_date, max_date = get_next_load_date(START_DATE) # "2026-04-12", "2026-04-25"
    min_date_obj = datetime.strptime(min_date, "%Y-%m-%d")
    max_date_obj = datetime.strptime(max_date, "%Y-%m-%d")

    # data has been fully loaded
    if min_date_obj >= max_date_obj:
        logger.info(f"No new data to load. Data up to date {max_date}")
        return {
            "status": "skipped",
            "message": "No new data",
        }

    logger.info(f"Processing data for {len(companies)} companies from {min_date} to {max_date}")

    # Extract to parquet, then load to DuckDB for each company
    results = []
    for company in COMPANIES:

        try:
            parquet_path = extract_complaint_to_landing(
                company=company,
                min_date=min_date,
                max_date=max_date
            )

            # if no complaints extracted for the company in the date range
            row_count = pq.read_table(parquet_path).num_rows
            if row_count == 0:
                logger.info(f"No complaints extracted for {company}. Skipping loading to DuckDB")
                results.append(
                    {
                        "company": company,
                        "status": "success",
                        "date_range": f"{min_date} to {max_date}",
                        "info": "No complaints found"
                    }
                )
                continue
            
            # Load the Parquet file into DuckDB
            result = load_landing_to_duckdb(
                parquet_path=parquet_path,
                database_path=database_path
            )
            result["company"] = company
            result["date_range"] = f"{min_date} to {max_date}"
            results.append(result)

        except Exception as e:
            logger.error(f"Failed to load data for {company}: {e}")
            results.append(
                {
                    "company": company,
                    "status": "failed",
                    "error": str(e)
                }
            )




    @task
    def run_dbt_models(data, ds):
        """Transform data from Bronze to Silver layer

        data: data to transform (JSON file)
        ds: the date that Airflow runs the task
        """

        # For simplicity, we just pass the data through without transformation
        return data


    @task
    def run_dbt_tests(data, ds):
        pass


    @task
    def generate_reports():
        pass

    
    load_raw_to_duckdb(extract_to_parquet())


cfpb_complaint_daily_dag()