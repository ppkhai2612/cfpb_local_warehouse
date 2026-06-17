# Local Warehouse for CFPB Complaint Data

This project implements a pipeline that retrieves **consumer complaint data** from the CFPB API, this data then is stored in a **local data warehouse**. dbt is used to transform data into analytics-ready models, and serves interactive dashboards

* **Python Package Manager**: [uv](https://docs.astral.sh/uv/)
* **Data Ingestion**: [dlt](https://dlthub.com/product/dlt) + [PyArrow](https://arrow.apache.org/docs/python/index.html)
* **Raw Data Storage**: [MinIO](https://www.min.io/) (raw data in [Parquet](https://parquet.apache.org/) format)
* **Transformation**: [dbt-core](https://www.getdbt.com/) & [dbt-colibri](https://www.colibri-data.com/)
* **OLAP Database**: [DuckDB](https://duckdb.org/)
* **Orchestration**: [Airflow](https://airflow.apache.org/)
* **BI Tool**: [Streamlit](https://streamlit.io/)

## How to run the pipeline

1. **Install Python dependencies**: `uv sync --extra dev`
2. **Configuration setting**: Edit `src/cfpb/config.py` to configure `START_DATE`, which is the date the data is included in. **Recommended**: `START_DATE` should be within the last three years from today to ensure the data is not stale. Example

    ```python
    START_DATE = "2026-06-01"
    ```

3. **Run pipeline**

4. **Run backfill pipeline** (optional running if you need to reprocess historical data for analytics)
- 

5. **Testing**

```bash
# Run Python tests
`uv run pytest tests/`
```



## Access UIs

- MinIO Console: http://localhost:9001
- Spark Web UI: http://localhost:8080
- Airflow Web UI: http://localhost:8081


## Testing

Running etl.py script either one or two ways
- python -m src.etl.etl
or 
```python
export PYTHONPATH=$(pwd)
python src/etl/etl.py
```




