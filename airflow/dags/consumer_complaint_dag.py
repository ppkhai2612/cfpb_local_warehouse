from pathlib import Path
from datetime import datetime, timedelta
import logging
import sys

from airflow.sdk import dag, task

sys.path.insert(0, str(Path(__file__).parent.parent.parent)) # add root project dir to sys.path
from src.etl.etl import save_parquet_to_bronze, extract_complaints

from src.cfg.config import START_DATE, COMPANIES
logger = logging.getLogger(__name__)


@task()
def extract_to_minio():
    """Task for extract complaints and save it to bronze layer in MinIO as Parquet files"""
    complaints = extract_complaints(start_date=START_DATE, companies=COMPANIES)

    # If reaches this point, it's definitely a list of data (if list is not empty, write records to Minio)
    if complaints:
        save_parquet_to_bronze(complaints, start_date=START_DATE)



default_args = {
    'owner': 'khai',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=2)
}

@dag(
    'consumer_complaint_daily_dag',
    description='DAG is run daily to extract complaint data, load into modern lakehouse architecture to serve the business use cases',
    schedule='@daily',
    start_date=datetime(2026, 1, 1),
    default_args=default_args,
    catchup=False,
    tags=['cfpb']
)
def consumer_complaint_daily_dag():
    """Daily DAG for CFPB complaint pipeline

    E2E pipeline includes four tasks:
        1. Extracting data from CFPB API and load it into MinIO (Bronze layer)
        2. Transforming data with dbt run
        3. Data testing with dbt test
        4. Generating analytic report/dashboard
    """

    @task
    def run_dbt_models(data, ds):
        """Transform data from Bronze to Silver layer

        data: data to transform (JSON file)
        ds: the date that Airflow runs the task
        """

        # For simplicity, we just pass the data through without transformation
        return data


    @task
    def run_dbt_test(data, ds):
        pass


    @task
    def generate_report():
        pass

    extract_to_minio()


consumer_complaint_daily_dag()