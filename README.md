# CFPB Local Data Warehouse

## Purpose

This project builds a local analytics warehouse for Consumer Financial Protection Bureau (CFPB) consumer complaint data. It extracts complaint records from the CFPB API, lands the raw data in MinIO, converts the files to Parquet, loads them into DuckDB, transforms them with dbt, and exposes the final marts through a Streamlit dashboard.

The project is designed as a small end-to-end data platform that can run on a local
machine. It demonstrates how to:

- Ingest API data incrementally by complaint received date.
- Store raw and bronze data in object storage.
- Load analytical data into DuckDB for local OLAP workloads.
- Use dbt to build staging, intermediate, fact, dimension, and aggregate models.
- Orchestrate the workflow with Airflow.
- Explore complaint trends in a Streamlit app.

The main dataset is the CFPB Consumer Complaint Database.

## Architecture And Data Stack

![Project architecture](images/architecture.png)

### Data Flow

```text
CFPB API
  -> raw JSONL files in MinIO
  -> bronze Parquet files in MinIO
  -> DuckDB raw.cfpb_complaints
  -> dbt staging/intermediate/marts models
  -> Streamlit dashboards
```

### Project Components

- `src/cfpb/cfpb_client.py`: CFPB API client with pagination support.
- `src/cfpb/ingestion_pipeline.py`: ingestion helpers for raw, bronze, and DuckDB loads.
- `airflow/dags/cfpb_complaint_dag.py`: daily Airflow DAG that orchestrates the pipeline.
- `dbt_cfpb/models/`: dbt models for staging, intermediate logic, and marts.
- `streamlit/app.py`: dashboard app that reads from the DuckDB marts schema.
- `database/cfpb_complaints.duckdb`: local DuckDB database created by the pipeline.
- `docker-compose.yml`: local MinIO service with `raw` and `bronze` buckets.

### Tools Used

- Python and `uv` for dependency management.
- `requests` for CFPB API calls.
- PyArrow for JSONL and Parquet processing.
- MinIO for local S3-compatible object storage.
- DuckDB for the local analytical database.
- dbt Core and dbt DuckDB for transformations.
- Airflow for orchestration.
- Streamlit and Plotly for dashboards.

## How To Run The Project

### 1. Install Dependencies

Install the Python dependencies from the project root:

```bash
uv sync --extra dev
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```bash
MINIO_ROOT_USER="minioadmin"
MINIO_ROOT_PASSWORD="minioadmin"
AIRFLOW_USERNAME="admin"
AIRFLOW_PASSWORD="admin"
```

The current MinIO service uses an AIStor image and expects a license file at:

```text
$HOME/minio/minio.license
```

If you use a different MinIO image, update `docker-compose.yml` accordingly.

### 3. Start MinIO

```bash
docker compose up -d
```

MinIO will create two buckets automatically:

- `raw`
- `bronze`

MinIO Console: `http://localhost:9001`

### 4. Start Airflow

```bash
./start_airflow.sh
```

Airflow runs at:

```text
http://localhost:8081
```

Sign in with the `AIRFLOW_USERNAME` and `AIRFLOW_PASSWORD` values from `.env`.

### 5. Run The Ingestion Pipeline

Open Airflow and unpause the DAG:

```text
cfpb_complaint_daily_dag
```

The DAG is scheduled daily. For each run, it processes complaints for the previous
logical date and performs these tasks:

1. Extract CFPB complaints and write JSONL files to `raw/cfpb_complaints/<date>/`.
2. Convert raw JSONL files to Parquet files in `bronze/cfpb_complaints/<date>/`.
3. Upsert bronze Parquet records into `raw.cfpb_complaints` in DuckDB.
4. Run dbt models.
5. Run dbt tests.

For screenshots and examples of normal runs, catchup runs, and backfills, see
[`docs/run_dag_guide.md`](docs/run_dag_guide.md).

### 6. Run dbt Manually

The Airflow DAG runs dbt automatically, but you can also run dbt from the project root:

```bash
cd dbt_cfpb
uv run dbt run
uv run dbt test
```

The dbt profile points to:

```text
../database/cfpb_complaints.duckdb
```

### 7. Start The Dashboard

After the DAG and dbt models have run successfully, start Streamlit:

```bash
uv run streamlit run streamlit/app.py
```

By default, Streamlit runs at:

```text
http://localhost:8501
```

### 8. Run Tests

```bash
uv run pytest tests/
```

You can also run linting and formatting checks:

```bash
uv run ruff check .
uv run ruff format --check .
```

## Notes

- If the Airflow DAG has `catchup=True`, so a newly unpaused DAG may create historical runs from its configured `start_date`.
- Raw and bronze data are stored in MinIO; modeled analytics tables are stored in DuckDB.
- The Streamlit dashboard expects dbt mart tables under the `marts` schema.