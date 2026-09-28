"""Run CFPB complaints incremental pipeline using Prefect.

This is an end-to-end ELT pipeline that:
1. Extract & Load (EL):
    - Extracts data from START_DATE once (initial load)
    - Then appends data for each new day (incremental load)
    - Works for companies in src/cfg/config.py
2. Transform (T):
    - Runs all dbt models (staging -> intermediate -> marts)
    - Creates fact tables, dimension tables, and aggregations
3. Test:
    - Validates data quality with dbt tests

Usage:
    python run_prefect_flow.py [--database DATABASE_PATH] [--reset-state]

Examples:
    # Run the pipeline (incremental load + dbt transformations)
    python run_prefect_flow.py

    # Use a different database file
    python run_prefect_flow.py --database my_data.duckdb

    # Reset state to reload all data from START_DATE
    python run_prefect_flow.py --reset-state
"""

import argparse
import logging
import sys
from pathlib import Path

from src.orchestration.cfpb_flows import cfpb_complaints_incremental_flow


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main entrypoint for the Prefect flow with dbt transformations."""
    parser = argparse.ArgumentParser(
        description="Run CFPB Consumer Complaints ELT Pipeline with Prefect and dbt"
    )
    parser.add_argument(
        "--database",
        type=str,
        default="database/cfpb_complaints.duckdb",
        help="Path to DuckDB database file (default: database/cfpb_complaints.duckdb)"
    )
    parser.add_argument(
        "--reset-state",
        action="store_true", # if use this arg, its value is set to True
        help="Reset state file to trigger initial load from START_DATE"
    )

    args = parser.parse_args()

    if args.reset_state:
        from src.utils.state import reset_state

        print("Resetting pipeline state...", flush=True)
        reset_state()
        print("State has been reset. Next run will perform initial load.", flush=True)
        logger.info("State has been reset. Next run will perform initial load.")
        return 0

    try:
        logger.info("Starting ELT pipeline: Extract & Load -> Transform -> Test")
        result = cfpb_complaints_incremental_flow(
            database_path=args.database
        ) # run the pipeline

        if result is None:
            logger.error("Flow returned None - this should not happen")
            return 1

        logger.info("Flow completed successfully")
        logger.info(f"Summary: {result}")

        # Handle skipped flows (no new data to load)
        if result.get("status") == "skipped":
            logger.info(f"Flow skipped: {result.get('message', 'No new data')}")
            return 0

        # Check if dbt transformations succeeded
        dbt_run = result.get("dbt_run")
        if dbt_run:
            dbt_status = dbt_run.get("status")
            if dbt_status == "failed":
                logger.warning("dbt transformations failed - check logs above")
                return 1
                
        return 0
    
    except Exception as e:
        logger.error(f"Flow execution failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())