"""Script to run (incremental) data pipeline

This is an end-to-end ELT pipeline that

1. Extract & Load (EL)
    - Extracts data from START_DATE once (initial load)
    - Then appends data for each new day (incremental loads)
    - Works for companies configured in src/config.py
    - Raw data is stored in MinIO (data partitioned by date)
2. Transform (T)
    - For transformation, data from MinIO will be loaded into DuckDB, using dbt as transformation layer
    - Runs dbt models (staging -> intermediate -> marts)
    - Creates fact, dimension, and aggregation tables in DuckDB
3. Tests
    - If dbt run successfully, performs data quality checks with dbt tests

Usage:
    python run_pipeline.py [--database DATABASE_PATH] [--reset-state]

Examples:
    # Run the pipeline
    python run_pipeline.py

    # Use a different database file
    python run_pipeline.py --database my_database.duckdb

    # Reset state that reload all data from START_DATE
    python run_pipeline.py --reset-state
"""

import argparse
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "airflow"))
from dags.cfpb_complaint_dag import cfpb_complaint_daily_dag

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main entrypoint for the Airflow DAG"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database",
        type=str,
        default="database/cfpb_complaints.duckdb",
        help="Path to the DuckDB database file (default: database/cfpb_complaints.duckdb)"
    )
    parser.add_argument(
        "--reset-state",
        action="store_true",
        help="Reset state file to trigger initial load from START_DATE"
    )

    args = parser.parse_args()

    if args.reset_state:
        
        from src.utils.state import reset_state
        logger.info("Resetting the pipeline state...")
        reset_state()
        logger.info("State is reset. Next run will perform initial load.")
        return 0
    
    try:
        logger.info("Starting ELT pipeline")
        result = cfpb_complaint_daily_dag(
            database_path=args.database
        )

        # Handle the case where the pipeline returns None
        if result is None:
            logger.error("An unexpected error occurred while the pipeline was running")
            return 1

        logger.info("Pipeline completed successfully")
        logger.info(f"Summary: {result}")

        # Handle skipped pipeline (no new data to load)
        if result.get("status") == "skipped":
            logger.info(f"Pipeline skipped: {result.get('message', 'No new data')}")
            return 0

        # Check if dbt transformations was successful
        dbt_run = result.get("dbt_run")
        if dbt_run:
            dbt_status = dbt_run.get("status")
            if dbt_status == "failed":
                logger.warning("dbt transformations failed, check logs above")
                return 1

        return 0

    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())