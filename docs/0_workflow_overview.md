# CFPB Complaints Pipeline – Workflow Overview

## 1. Flow Entry

**Source code**: `src/orchestration/cfpb_flows.py` -> `cfpb_complaints_incremental_flow()`

This is the main Prefect flow. It:

- Determines the load window using `get_next_load_date()`

    -> File: `src/utils/state.py`

- Reads `COMPANIES` from config

    -> File: `src/cfg/config.py`

- Loops through each company and calls the Extract+Load task

## 2. Extract to Parquet (per company)

**Source code**: `src/orchestration/cfpb_flows.py` -> `extract_to_parquet_task()` -> `save_to_parquet()` -> `extract_complaints()`

Calls the CFPB API via `extract_complaints()` and writes results as a Parquet file to the landing area: `landing/cfpb_complaints/{company}_{date_min}_{date_max}.parquet`

This step handles **Extract -> Stage**.

## 3. Load Parquet to DuckDB (per company)

**Source code**: `src/orchestration/cfpb_flows.py` -> `load_parquet_to_duckdb_task()` -> `load_parquet_to_duckdb()`

Reads the staged Parquet file and loads it into DuckDB via dlt (preserving merge/dedup logic): `database/cfpb_complaints.duckdb`

This step handles **Stage -> Load**.

## 4. Update Incremental State

**Source code**: `src/utils/state.py` -> `update_last_loaded_date(date_max)`

If all companies (extract+load) completed successfully, updates `pipeline_state.json`, enabling:
- Incremental loading on next run
- Avoiding reprocessing old data

## 5. Transform with dbt

**Source code**: `src/orchestration/cfpb_flows.py` -> `run_dbt_models_task()`

Run SQL models by layers

## 6. Test with dbt

**Source code**: `src/orchestration/cfpb_flows.py` -> `run_dbt_tests_task()`

Run tests on dbt models

## 7. Serve dashboards with dbt Charts

