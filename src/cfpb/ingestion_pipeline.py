"""dlt Ingestion Pipeline

This pipeline extracts consumer complaint data from the CFPB API
and loads it into DuckDB
"""

import logging
import json
import os
from datetime import datetime
from typing import Any
from collections.abc import Iterator
from pathlib import Path

from dotenv import load_dotenv
import pyarrow as pa
import pyarrow.json as pajson
import pyarrow.parquet as pq
from pyarrow import fs
import duckdb

from .cfpb_client import CFPBClient


logger = logging.getLogger(__name__)
load_dotenv() # add env vars from .env to os.environ


def extract_complaints(date) -> Iterator[list[dict[str, Any]]]:
    """Extract complaints from CFPB API by date

    Args:
        date (str): The date that the data was extracted

    Yields:
        An enriched chunk of records
    """
    client = CFPBClient() # init the client

    try:
    
        logger.info(f"Extracting all complaints for the date {date}")
        extraction_timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        
        for chunk in client.get_complaints(date_received_min=date, date_received_max=date):
            
            # add "extracted_at" to each dict
            enriched_chunk = [{**item, "extracted_at": extraction_timestamp} for item in chunk]
            yield enriched_chunk  # yield enriched chunk

    finally:
        client.close() # close the connection to the API client


def load_to_raw(
    complaints: list[dict[str, Any]],
    date: str,
    partition: int,
    bucket_name: str = "raw"
):
    """Load complaints to raw bucket in MinIO

    Args:
        complaints (list[dict[str, Any]]): list of complaints
        date (str): the date the data was processed
        partition (int): The nth partition is currently being written to
        bucket_name (str, optional): Bucket name in MinIO. Defaults to "raw"
    """
    logger.info(f"Loading {len(complaints)} complaints to {bucket_name} bucket in MinIO")
    minio_client = _get_minio_fs() # MinIO client
    object_path = f"{bucket_name}/cfpb_complaints/{date}/part_{partition}.jsonl"

    try:
        with minio_client.open_output_stream(object_path) as out:
            for complaint in complaints:
                out.write(json.dumps(complaint, ensure_ascii=False).encode("utf-8"))
                out.write(b"\n")
            print(f"Upload succesfully: {len(complaints)} complaints (Partition {partition})")

    except Exception as e:
        print(f"Error when uploading: {e}")
        raise


def load_to_bronze(
    raw_prefix: str,
    process_date: str,
    partitions: int
):
    """Load data from raw layer (jsonl files) to bronze layer (parquet files)

    Args:
        raw_prefix (str):  (e.g., raw/cfpb_complaints/{YYYY-MM-DD})
        process_date (str): the date the data was processed
        partitions (int): The data is partitioned into n files in bronze
    """

    # file selector
    selector = fs.FileSelector(
        raw_prefix,
        recursive=False,
    )

    minio_client = _get_minio_fs()
    for info in minio_client.get_file_info(selector):
        if not info.path.endswith(".jsonl"):
            continue

        # read data from raw 
        with minio_client.open_input_file(info.path) as f:
            table = pajson.read_json(f)

        # write data to bronze 
        output = (
            info.path
                .replace("raw/", "bronze/")
                .replace(".jsonl", "parquet")
        )
        with minio_client.open_output_stream(output) as out:
            pq.write_table(table, out, compression="snappy")


def load_parquet_to_duckdb(
    parquet_path: str,
    database_path: str,
    schema_name: str = "raw",
) -> dict[str, Any]:
    """Load a parquet file into DuckDB natively, preserving merge/dedup logic.
    
    Args:
        parquet_path: Path to the parquet file to load
        database_path: Path to DuckDB database file
        schema_name: Schema name for the data
        
    Returns:
        Dictionary with load info
    """
    # ensure the database directory exists
    db_path = Path(database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    with duckdb.connect(str(db_path.absolute())) as conn:
        # httpfs extension for interacting file system
        conn.execute("INSTALL httpfs; LOAD httpfs;")

        # Authentication so that DuckDB can access MinIO
        minio_access_key_id = os.environ["MINIO_ROOT_USER"]
        minio_secret_access_key = os.environ["MINIO_ROOT_PASSWORD"]
        minio_endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
        conn.execute(f"""
            CREATE OR REPLACE SECRET minio_secret (
                TYPE s3,
                PROVIDER config,
                KEY_ID {os.environ["MINIO_ROOT_USER"]},
                SECRET {os.environ["MINIO_ROOT_PASSWORD"]},
                REGION 'us-east-1',
                USE_SSL false,
                ENDPOINT '{minio_endpoint}',
                URL_STYLE 'path',
            );
            """
        )           
            
        # create schema
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name};")
        table_name = f"{schema_name}.cfpb_complaints"
        table_exists = conn.execute(
            f"SELECT 1 FROM information_schema.tables WHERE table_schema = '{schema_name}' AND table_name = 'cfpb_complaints'"
        ).fetchone()
        
        if not table_exists:
            logger.info(f"Creating new table {table_name} with primary key 'complaint_id'")
            # create table with schema
            conn.execute(f"""
                CREATE TABLE {table_name} AS 
                SELECT * FROM read_parquet('{parquet_path}') LIMIT 0;
            """)
            conn.execute(f"ALTER TABLE {table_name} ADD PRIMARY KEY (complaint_id);") # add primary key
            
        # Merge/upsert logic
        logger.info(f"Merging parquet files from S3: {parquet_path}")
        conn.execute(f"""
            INSERT OR REPLACE INTO {table_name} 
            SELECT * FROM read_parquet('{parquet_path}');
        """)
        
        # 
        parquet_count = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{parquet_path}')").fetchone()[0]
        total_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        
    logger.info(f"DONE! Total records in MinIO: {parquet_count}. Total records in DB: {total_count}")
    # return {
    #     "records_processed_from_s3": parquet_count,
    #     "total_records_in_table": total_count,
    #     "status": "success"
    # }


def _get_minio_fs():
    """Initialize a MinIO client

    Returns:
        Authenticated MinIO client
    """
    minio_fs = fs.S3FileSystem(
        access_key=os.environ["MINIO_ROOT_USER"],
        secret_key=os.environ["MINIO_ROOT_PASSWORD"],
        scheme="http",
        endpoint_override="localhost:9000"
    )
    return minio_fs


# if __name__ == "__main__":
#     client = CFPBClient()
#     for chunk in client.get_complaints(date_received_min="2026-06-01", date_received_max="2026-06-01"):
#         print(chunk)