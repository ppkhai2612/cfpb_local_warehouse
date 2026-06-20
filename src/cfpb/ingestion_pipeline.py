"""dlt Ingestion Pipeline

This pipeline extracts consumer complaint data from the CFPB API
and loads it into DuckDB
"""

import re
import logging
from datetime import datetime
import io
import os
from typing import Any
from collections.abc import Iterator

import dlt
from dotenv import load_dotenv
import pandas as pd
import pyarrow as pa
from pyarrow import fs
from dlt.destinations import duckdb
import pyarrow.parquet as pq
from minio import Minio

from cfpb_client import CFPBClient
# from ..state import get_next_load_date, update_last_loaded_date
from pathlib import Path


logger = logging.getLogger(__name__)
load_dotenv() # add env vars from .env to os.environ


@dlt.resource(
    name="cpfb_complaints",
    write_disposition="merge",
    primary_key="complaint_id"
)
def extract_complaints(
    date_received_min: str | None = None,
    date_received_max: str | None =None,
    company_name: str | None = None
) -> Iterator[dict[str, Any]]:
    """Extract complaints from CFPB API

    Args:
        date_received_min (str | None, optional): Minimum received date. Defaults to None.
        date_received_max (str | None, optional): Maximum received date. Defaults to None.
        company_name (str | None, optional): Company name to filter. Defaults to None.

    Yields:
        Complaint records from CFPB API
    """
    client = CFPBClient()

    try:
        # if company name is provided, extract complaints only for that company
        if company_name:
            logger.info(f"Extracting complaints for company {company_name}")
            complaints = client.get_complaints_by_company(
                company=company_name,
                date_received_min=date_received_min,
                date_received_max=date_received_max
            )
        else: # otherwise, extract all complaints
            logger.info(f"Extracting all complaints")
            complaints = client.get_complaints(
                date_received_min=date_received_min,
                date_received_max=date_received_max
            )

        # add extraction timestamp for each complaint
        extraction_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for complaint in complaints:
            complaint["_dlt_extracted_at"] = extraction_timestamp
            yield complaint
    
    finally: # ensure the client is closed even if an error occurs
        client.close()


def save_parquet_to_landing(
    date_received_min: str,
    date_received_max: str,
    company_name: str,
    bucket_name: str = "raw"
) -> str | None:
    """Save raw data to MinIO (works as landing area) in Parquet format
    Path to Parquet file in MinIO has the following format:
        s3://raw/cfpb_complaints/YYYY-MM-DD/{company_name}_{date_received_min}_{date_received_max}.parquet

    Args:
        date_received_min (str): Minimum received date (YYYY-MM-DD)
        date_received_max (str): Maximum received date (YYYY-MM-DD)
        company_name (str): Company name to filter
        bucket_name (str): MinIO bucket name to save data (default: "raw")

    Returns:
        str | None: Path to the written Parquet file in MinIO
                    or None if no records were extracted
    """
    # extract complaints from CFPB API
    records = list(
        extract_complaints(
            date_received_min=date_received_min,
            date_received_max=date_received_max,
            company_name=company_name
        )
    )

    # define file path to write to
    landing_dir = datetime.now().strftime("%Y-%m-%d")
    safe_company = _sanitize_company_name(company_name)
    filename = f"{safe_company}_{date_received_min}_{date_received_max}.parquet"
    object_key = "cfpb_complaints/" + landing_dir + "/" + filename
    file_path = bucket_name  + "/" + object_key

    # PyArrow Table
    if records:
        table = pa.Table.from_pylist(records)
    else:
        table = pa.table({"_empty": pa.array([], type=pa.bool_())}) # _empty is a column
        logger.info(f"No records extracted for company {company_name}, writing empty parquet")
    
    # Write data to MinIO
    try:
        # minio_client = _get_minio_client()

        minio_fs = fs.S3FileSystem(
            access_key=os.environ["MINIO_ROOT_USER"],
            secret_key=os.environ["MINIO_ROOT_PASSWORD"],
            scheme="http",
            endpoint_override="localhost:9000"
        )
        
        with minio_fs.open_output_stream(file_path) as stream:
            pq.write_table(
                table, 
                stream,
                # row_group_size=100000 # Controls memory chunking
            )

        logger.info(f"Wrote {len(records)} records to {file_path}")

        # unique_companies = df['company'].unique() # get unique name of companies
        # parquet_paths = []
        # for company in unique_companies:
        #     company_df = df[df['company'] == company]

        #     # WRITE TO LANDING AREA
        #     raw_data_dir = f"landing/cfpb_complaints/{landing_date}"
        #     os.makedirs(raw_data_dir, exist_ok=True)
        #     raw_data_path = os.path.join(raw_data_dir, f"{standardize_company_name(company)}_{min_date}_{max_date}.jsonl")
        #     company_df.to_json(raw_data_path, orient='records', lines=True)
        #     logger.info(f"Saved raw JSON data for company '{company}' to {raw_data_path}")

        #     # WRITE TO MINIO

        #     # write DataFrame to buffer
        #     buffer = io.BytesIO()
        #     company_df.to_parquet(buffer, index=False)

        #     # seek: move to a specific byte in the file
        #     buffer.seek(0, 2)
        #     size = buffer.tell() # get size of file in bytes
        #     buffer.seek(0)

        #     # prepare the path
        #     # Example: s3://raw/cfpb_complaints/2026-04-24/filename.parquet
            
        #     filename = f"{safe_company}_{min_date}_{max_date}.parquet"
        #     object_key = f"cfpb_complaints/{layer_name}/{landing_date}/{filename}"
            
        #     # print(f"DEBUG: Processing company '{company}' -> Key: {object_key}")
        #     # write data from buffer to object
        #     client.put_object(
        #         bucket_name=bucket,
        #         object_name=object_key,
        #         data=buffer,
        #         length=size
        #     )

        #     logger.info(f"Wrote data to s3://{bucket}/{object_key}")
        #     parquet_paths.append(f"s3://{bucket}/{object_key}")

        return file_path

    except S3Error as exc:
        logger.error(f"Failed to write data to MinIO: {exc}")
        raise
    

def _get_minio_client():
    """Initialize a MinIO client

    Returns:
        Authenticated MinIO client
    """
    client = Minio(
        'localhost:9000',
        access_key=os.environ['MINIO_ROOT_PASSWORD'],
        secret_key=os.environ['MINIO_ROOT_PASSWORD'],
        secure=False,
        region='us-east-1'
    )
    return client

def _sanitize_company_name(name: str) -> str:
    """Sanitizing the company name, which is used in filename
    
    Args:
        name (str): A company name to sanitize (e.g., Early Warning Services, LLC)

    Returns:
        str: A sanitized company name (e.g., early_warning_services__llc)
    """
    return re.sub(r"[^a-z0-9_]", "_", name.strip().strip('.').lower())


def load_parquet_to_duckdb(
    parquet_path: str,
    database_path: str = 'database/cfpb_complaints.duckdb',
) -> dict[str, Any]:
    """Load a parquet file into DuckDB via dlt
    
    Params:
        parquet_path: Path to parquet file to load
        database_path: Path to DuckDB database file

    Returns:
        Dictionary with load info
    """
    # read parquet file
    table = pq.read_table(parquet_path)
    records = table.to_pylist()
    logger.info(f"Read {len(records)} records from {parquet_path}")
    
    pipeline = create_pipeline(database_path=database_path)

    @dlt.resource(
        name="cpfb_complaints",
        write_disposition="merge",
        primary_key="complaint_id"
    )
    def parquet_resource() -> Iterator[dict[str, Any]]:
        yield from records # equivalent to loop through each element in the list and yield it

    # run the pipeline
    load_info = pipeline.run(parquet_resource())
    logger.info(f"Loaded {len(records)} records into DuckDB")
    return {"records_loaded": len(records), "load_info": str(load_info)}


def create_pipeline(
    database_path: str = 'database/cfpb_complaints.duckdb',
    schema_name: str = 'raw'
) -> dlt.Pipeline:
    """Create a dlt pipeline for loading data to DuckDB
    
    Params:
        database_path: Path to DuckDB database file
        schema_name: Name of the schema to load data into (default: raw)

    Returns:
        dlt.Pipeline object
    """

    # Ensure database directory exists
    db_path = Path(database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Create pipeline with DuckDB destination
    pipeline = dlt.pipeline(
        pipeline_name = "cfpb_complaints",
        destination=duckdb(str(db_path.absolute())),
        dataset_name=schema_name,
    )

    return pipeline



if __name__ == "__main__":
    # Example usage
    # start_date = "2026-04-12"
    # companies = ["Kriya Capital, LLC", "NAVY FEDERAL CREDIT UNION"]
    # complaints = extract_complaints(start_date, companies)
    # save_parquet_to_bronze(complaints, start_date)
    save_parquet_to_landing(
        date_received_min="2026-04-01",
        date_received_max="2026-04-10",
        company_name="Kriya Capital, LLC"
    )