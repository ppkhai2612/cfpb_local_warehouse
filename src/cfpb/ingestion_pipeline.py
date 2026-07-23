"""CFPB complaint ingestion helpers.

The pipeline extracts complaint records from the CFPB API, stores raw JSONL in
MinIO, converts that raw data to bronze Parquet, and upserts it into DuckDB.
"""

import json
import logging
import os
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
from dotenv import load_dotenv
import pyarrow as pa
import pyarrow.json as pajson
import pyarrow.parquet as pq
from pyarrow import fs

from .cfpb_client import CFPBClient


logger = logging.getLogger(__name__)
load_dotenv()

DEFAULT_BUCKET = "raw"
COMPLAINTS_PREFIX = "cfpb_complaints"
DUCKDB_SCHEMA = "raw"

CFPB_SCHEMA = pa.schema(
    [
        ("product", pa.string()),
        ("complaint_what_happened", pa.string()),
        ("date_sent_to_company", pa.timestamp("ms", tz="UTC")),
        ("issue", pa.string()),
        ("sub_product", pa.string()),
        ("zip_code", pa.string()),
        ("tags", pa.string()),
        ("has_narrative", pa.bool_()),
        ("complaint_id", pa.int64()),
        ("timely", pa.string()),
        ("company_response", pa.string()),
        ("submitted_via", pa.string()),
        ("company", pa.string()),
        ("date_received", pa.timestamp("ms", tz="UTC")),
        ("state", pa.string()),
        ("company_public_response", pa.string()),
        ("sub_issue", pa.string()),
        ("extracted_at", pa.timestamp("ms", tz="UTC")),
    ]
)


def extract_complaints(process_date: str) -> Iterator[list[dict[str, Any]]]:
    """Yield CFPB complaints received on a single date.

    Args:
        process_date: Date to fetch from the CFPB API, formatted as YYYY-MM-DD.

    Yields:
        Chunks of complaint records with an ``extracted_at`` timestamp added.
    """
    client = CFPBClient()
    extracted_at = _utc_now_iso()

    try:
        logger.info("Extracting complaints for %s", process_date)
        for chunk in client.get_complaints(
            date_received_min=process_date,
            date_received_max=process_date,
        ):
            yield [{**complaint, "extracted_at": extracted_at} for complaint in chunk]

    finally:
        client.close()


def load_to_raw(
    complaints: list[dict[str, Any]],
    process_date: str,
    partition: int,
    bucket_name: str = DEFAULT_BUCKET,
) -> str:
    """Write one complaint chunk to raw JSONL storage.

    Args:
        complaints: Complaint records to write.
        process_date: Date partition for the output path.
        partition: One-based chunk number.
        bucket_name: MinIO bucket name.

    Returns:
        The object path written in MinIO.
    """
    minio_client = _get_minio_fs()
    object_path = _complaints_object_path(
        bucket_name=bucket_name,
        process_date=process_date,
        partition=partition,
        suffix="jsonl",
    )

    try:
        with minio_client.open_output_stream(object_path) as out:
            for complaint in complaints:
                out.write(json.dumps(complaint, ensure_ascii=False).encode("utf-8"))
                out.write(b"\n")

    except Exception:
        logger.exception("Failed to upload raw complaints to %s", object_path)
        raise

    logger.info(
        "Uploaded %s complaints to %s",
        len(complaints),
        object_path,
    )
    return object_path


def load_to_bronze(raw_prefix: str, process_date: str, partitions: int) -> list[str]:
    """Convert raw JSONL complaint files to bronze Parquet files.

    Args:
        raw_prefix: Prefix containing raw JSONL files, for example
            ``raw/cfpb_complaints/YYYY-MM-DD``.
        process_date: Date partition being processed.
        partitions: Expected number of raw partitions.

    Returns:
        Paths of the Parquet files written.
    """
    logger.info(
        "Converting %s raw partition(s) for %s from %s",
        partitions,
        process_date,
        raw_prefix,
    )

    selector = fs.FileSelector(raw_prefix, recursive=False)
    minio_client = _get_minio_fs()
    parquet_paths: list[str] = []

    for info in minio_client.get_file_info(selector):
        if not info.path.endswith(".jsonl"):
            continue

        with minio_client.open_input_file(info.path) as f:
            table = pajson.read_json(f)

        table = normalize_table(table, CFPB_SCHEMA)
        output_path = info.path.replace("raw/", "bronze/").replace(".jsonl", ".parquet")

        with minio_client.open_output_stream(output_path) as out:
            pq.write_table(table, out, compression="snappy")

        parquet_paths.append(output_path)
        logger.info("Wrote bronze parquet file to %s", output_path)

    return parquet_paths


def load_parquet_to_duckdb(
    parquet_path: str,
    database_path: str,
    schema_name: str = DUCKDB_SCHEMA,
) -> dict[str, Any]:
    """Upsert Parquet complaint data into DuckDB.

    Args:
        parquet_path: S3 path or glob for the Parquet files to load.
        database_path: Path to the DuckDB database file.
        schema_name: DuckDB schema name for the target table.

    Returns:
        Load summary with source and target record counts.
    """
    db_path = Path(database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(str(db_path.absolute())) as conn:
        conn.execute("INSTALL httpfs; LOAD httpfs;")
        _configure_duckdb_minio_secret(conn)

        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name};")
        table_name = f"{schema_name}.cfpb_complaints"
        table_exists = conn.execute(
            f"SELECT 1 FROM information_schema.tables WHERE table_schema = '{schema_name}' AND table_name = 'cfpb_complaints'"
        ).fetchone()

        if not table_exists:
            logger.info(
                "Creating new table %s with primary key complaint_id", table_name
            )
            conn.execute(f"""
                CREATE TABLE {table_name} AS 
                SELECT * FROM read_parquet('{parquet_path}') LIMIT 0;
            """)
            conn.execute(f"ALTER TABLE {table_name} ADD PRIMARY KEY (complaint_id);")

        logger.info("Merging Parquet data from %s", parquet_path)
        conn.execute(f"""
            INSERT OR REPLACE INTO {table_name} 
            SELECT * FROM read_parquet('{parquet_path}');
        """)

        parquet_count = conn.execute(
            f"SELECT COUNT(*) FROM read_parquet('{parquet_path}')"
        ).fetchone()[0]
        total_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

    logger.info(
        "DuckDB load complete. Source records: %s. Total records in DB: %s",
        parquet_count,
        total_count,
    )
    return {
        "records_processed_from_s3": parquet_count,
        "total_records_in_table": total_count,
        "status": "success",
    }


def normalize_table(table: pa.Table, schema: pa.Schema) -> pa.Table:
    """Return ``table`` with exactly the columns and types in ``schema``."""

    arrays = []

    for field in schema:
        if field.name in table.column_names:
            column = table[field.name]

            if not column.type.equals(field.type):
                column = column.cast(field.type)

            arrays.append(column)
        else:
            arrays.append(pa.nulls(len(table), type=field.type))

    return pa.Table.from_arrays(arrays, schema=schema)


def _get_minio_fs() -> fs.S3FileSystem:
    """Return an authenticated MinIO filesystem client."""

    return fs.S3FileSystem(
        access_key=os.environ["MINIO_ROOT_USER"],
        secret_key=os.environ["MINIO_ROOT_PASSWORD"],
        scheme="http",
        endpoint_override=os.environ.get("MINIO_ENDPOINT", "localhost:9000"),
    )


def _complaints_object_path(
    bucket_name: str,
    process_date: str,
    partition: int,
    suffix: str,
) -> str:
    """Build an object path for a partitioned complaint file."""

    return f"{bucket_name}/{COMPLAINTS_PREFIX}/{process_date}/part_{partition}.{suffix}"


def _utc_now_iso() -> str:
    """Return the current UTC timestamp in JSON-friendly ISO-8601 format."""

    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _configure_duckdb_minio_secret(conn: duckdb.DuckDBPyConnection) -> None:
    """Configure DuckDB credentials for reading Parquet files from MinIO."""

    minio_endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    conn.execute(
        """
        CREATE OR REPLACE SECRET minio_secret (
            TYPE s3,
            PROVIDER config,
            KEY_ID ?,
            SECRET ?,
            REGION 'us-east-1',
            USE_SSL false,
            ENDPOINT ?,
            URL_STYLE 'path'
        );
        """,
        [
            os.environ["MINIO_ROOT_USER"],
            os.environ["MINIO_ROOT_PASSWORD"],
            minio_endpoint,
        ],
    )


# if __name__ == "__main__":
#     client = CFPBClient()
#     for chunk in client.get_complaints(date_received_min="2026-06-01", date_received_max="2026-06-01"):
#         print(chunk)
