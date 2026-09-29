# CFPB Local Data Warehouse

A local-first data warehouse pipeline that extracts CFPB consumer complaint data, transforms it with dbt into analytics-ready models, and serves interactive dashboards—all running on your laptop with zero cloud dependencies.

- **Package Manager**: [uv](https://docs.astral.sh/uv/) (Python)
- **Ingestion**: [dlt](docs/1_dlt.md) + [PyArrow](docs/2_pyarrow.md) (API -> Parquet staging -> DuckDB)
- **Staging Format**: [Parquet](docs/2_pyarrow.md) (via PyArrow) in `landing/`
- **OLAP Database**: [DuckDB](docs/3_duckdb.md)
- **Transformation & Documentation**: [dbt](docs/4_dbt.md) & [dbt-colibri](docs/4_dbt.md)
- **Orchestration**: [Prefect](docs/5_prefect.md)
- **BI Tool**: [dbt Charts](docs/6_dbt_charts.md)
- **CI/CD**: [Github Action](docs/8_github_action.md)

![](images/architecture.png)

## 1. Quick Start

### 1.1. Setup

```bash
# Install dependencies
uv sync

# Install dev dependencies (for testing)
uv sync --extra dev
```

### 1.2. Configuration

Edit [src/cfg/config.py](src/cfg/config.py) to configure companies and start date:

```python
START_DATE = "2023-01-01"
COMPANIES = ["jpmorgan", "bank of america"]
```

### 1.3. Run the Pipeline

```bash
# Run incremental pipeline (first run loads from START_DATE to today)
uv run python run_prefect_flow.py

# Reset state to reload from START_DATE
uv run python run_prefect_flow.py --reset-state
```

### 1.4. Backfill Landing Area



### 1.5. Access Prefect UI (Optional)

```bash
# Start Prefect server
./start_prefect_server.sh

# Access UI at http://127.0.0.1:4200
```

![](images/prefect_ui.png)

### 1.6. Access DuckDB UI

Launch the DuckDB UI:

```bash
# run workflow first
duckdb -ui database/cfpb_complaints.duckdb

# Access UI at http://localhost:4213
```

![](images/duckdb_ui.png)

### 1.7. Access dbt Charts Dashboards


### 1.8. Generate dbt Lineage Reports with Colibri

Generate interactive data lineage reports to visualize how data flows through your dbt models:

```bash
# Navigate to the dbt project directory
cd cfpb_complaints

# Compile models and generate dbt documentation
dbt compile && dbt docs generate

# Generate lineage report
colibri generate
```

Open `cfpb_complaints/dist/index.html` in your browser to explore the interactive lineage visualization showing model dependencies, data flow, and column-level lineage.

## 2. Testing

```bash
# Run python tests
uv run pytest tests/
```
```bash
# Run dbt tests
cd cfpb_complaints
dbt test
```