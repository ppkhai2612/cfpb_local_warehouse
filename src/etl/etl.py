"""This script extracts consumer complaint data from the CFPB API"""

import logging
from datetime import datetime, timedelta
import io
import os

from dotenv import load_dotenv
import pandas as pd
from minio import Minio
from airflow.sdk.exceptions import AirflowSkipException

from src.api.cfpb_client import CFPBClient
from src.utils.utils import standardize_company_name, is_minio_running
from src.utils.state import get_next_load_date, update_last_loaded_date


logger = logging.getLogger(__name__)

load_dotenv() # add env vars from .env to os.environ

def extract_complaints(
    start_date: str,
    companies: list[str]
):
    """
    Extract complaints from CFPB API

    Params:
        start_date (YYYY-MM-DD): Start date to fetch data. If fetching data succesfully, its value will be updated
        companies: List of company names to filter complaints

    Returns:
        List of dicts: 
    """
    client = CFPBClient()

    min_date, max_date = get_next_load_date(start_date) # "2026-04-12", "2026-04-25"
    min_date_obj = datetime.strptime(min_date, "%Y-%m-%d")
    max_date_obj = datetime.strptime(max_date, "%Y-%m-%d")

    # data has been fully loaded
    if min_date_obj >= max_date_obj:
        logger.info("No new data to extract. All complaints are up to date.")
        raise AirflowSkipException()
    
    logger.info(f"Loading data for {len(companies)} companies from {min_date} to {max_date}")

    try:
        
        if companies:

            all_complaints = []
            for company in companies:
                logger.info(f"Extracting complaints for company: {company}")
                complaints = client.get_complaints(
                    company=company,
                    date_received_min=min_date,
                    date_received_max=max_date
                )
                all_complaints.extend(complaints)

            return all_complaints

        logger.info(f"Extracting all complaints")
        complaints = client.get_complaints(
            date_received_min=min_date,
            date_received_max=max_date
        )
        
        return complaints

    except Exception as e:
        logger.error(f"Failed to fetch data")
        raise
    
    finally: # ensure the client is closed even if an error occurs
        client.close()


def save_parquet_to_bronze(
    data: list[dict],
    start_date: str,
    layer_name: str = "bronze",
    bucket: str = "local-lakehouse"
):
    """
    Save extracted data to MinIO in Parquet format
    In addition, it will also write data to JSON files for data preview

    Params:
        data: extracted data to save
        start_date (YYYY-MM-DD): start date to fetch 
        layer_name: the layer to save data to (default: bronze)
        bucket: the bucket name in MinIO (default: local-lakehouse)
    """

    # minio client
    client = Minio(
        'localhost:9000',
        access_key=os.environ['AWS_ACCESS_KEY_ID'],
        secret_key=os.environ['AWS_SECRET_ACCESS_KEY'],
        secure=False,
        region='us-east-1'
    )

    # Get necessary info
    min_date, max_date = get_next_load_date(start_date)
    landing_date = datetime.now().strftime("%Y-%m-%d")
    
    # convert to Pandas DataFrame and add ingestion timestamp
    df = pd.DataFrame(data)
    df["extracted_at"] = datetime.now().strftime("%Y%m%d_%H%M%S")

    unique_companies = df['company'].unique() # get unique name of companies 
    for company in unique_companies:
        company_df = df[df['company'] == company]

        # Preview JSON data
        raw_data_dir = f"landing/cfpb_complaints/{landing_date}"
        os.makedirs(raw_data_dir, exist_ok=True)
        raw_data_path = os.path.join(raw_data_dir, f"{standardize_company_name(company)}_{min_date}_{max_date}.jsonl")
        company_df.to_json(raw_data_path, orient='records', lines=True)
        logger.info(f"Saved raw JSON data for company '{company}' to {raw_data_path}")

        if is_minio_running(client):

            # write DataFrame to buffer
            buffer = io.BytesIO()
            company_df.to_parquet(buffer, index=False)

            # seek: move to a specific byte in the file
            buffer.seek(0, 2)
            size = buffer.tell() # get size of file in bytes
            buffer.seek(0)

            # prepare the path
            # Example: s3://local-lakehouse/cfpb_complaints/bronze/2026-04-24/filename.parquet
            safe_company = standardize_company_name(company)
            filename = f"{safe_company}_{min_date}_{max_date}.parquet"
            object_key = f"cfpb_complaints/{layer_name}/{landing_date}/{filename}"
            
            print(f"DEBUG: Processing company '{company}' -> Key: {object_key}")

            # write data from buffer to object
            client.put_object(
                bucket_name=bucket,
                object_name=object_key,
                data=buffer,
                length=size
            )

            logger.info(f"Wrote data to s3://{bucket}/{object_key}")
    

if __name__ == "__main__":
    # Example usage
    start_date = "2026-04-12"
    companies = ["Kriya Capital, LLC", "NAVY FEDERAL CREDIT UNION"]
    complaints = extract_complaints(start_date, companies)
    save_parquet_to_bronze(complaints, start_date)