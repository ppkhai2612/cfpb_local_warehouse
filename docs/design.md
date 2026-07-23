# Pipeline Design Decisions

This document records the main decisions made when designing the CFPB local data
warehouse pipeline. It focuses on why the pipeline is structured this way, what
trade-offs were accepted, and which improvements are intentionally left for later.

## Design Goals

- Run the full pipeline on a local machine.
- Keep the source data replayable instead of loading only directly into DuckDB.
- Separate ingestion, storage, warehouse loading, transformation, and dashboarding.
- Make daily runs and Airflow catchup runs easy to reason about.
- Use simple tools that are realistic for production-style analytics workflows.

## End-To-End Flow

```text
CFPB API
  -> raw JSONL files in MinIO
  -> bronze Parquet files in MinIO
  -> DuckDB raw.cfpb_complaints
  -> dbt staging, intermediate, and marts models
  -> Streamlit dashboard
```

## Decision 1: Use A Layered Pipeline

The pipeline is split into raw, bronze, warehouse, transformation, and dashboard
layers.

| Layer | Tool | Responsibility |
| --- | --- | --- |
| Source | CFPB API | Provides complaint records by received date |
| Raw | MinIO + JSONL | Stores extracted API records with minimal changes |
| Bronze | MinIO + Parquet | Stores typed, columnar files for faster reads |
| Warehouse | DuckDB | Stores the upserted analytical source table |
| Transformation | dbt | Builds staging, intermediate, fact, dimension, and aggregate models |
| Serving | Streamlit | Reads dbt marts for dashboarding |

This structure makes the pipeline easier to debug. If a downstream model fails,
the raw and bronze files still exist and can be reprocessed.

## Decision 2: Store Raw API Output Before Loading DuckDB

The pipeline does not load CFPB API responses directly into DuckDB.

Direct loading would be simpler:

```text
CFPB API -> DuckDB
```

The chosen design is:

```text
CFPB API -> JSONL -> Parquet -> DuckDB
```

Reasoning:

- Raw files provide an audit trail of what was extracted.
- Failed bronze or DuckDB loads can be rerun without calling the API again.
- Schema normalization is isolated from extraction.
- Object storage keeps ingestion and analytical storage loosely coupled.

Trade-off:

- The pipeline has more steps and more storage paths to manage.
- For a small personal project, direct DuckDB loading would be faster to build.

## Decision 3: Use MinIO As Local Object Storage

MinIO is used because it provides an S3-compatible storage layer locally.

Reasoning:

- It mirrors common lakehouse patterns without requiring a cloud account.
- PyArrow and DuckDB can read from S3-compatible paths.
- Separate `raw` and `bronze` buckets make storage responsibilities explicit.

Current buckets:

```text
raw
bronze
```

Current object layout:

```text
raw/cfpb_complaints/YYYY-MM-DD/part_1.jsonl
raw/cfpb_complaints/YYYY-MM-DD/part_2.jsonl

bronze/cfpb_complaints/YYYY-MM-DD/part_1.parquet
bronze/cfpb_complaints/YYYY-MM-DD/part_2.parquet
```

## Decision 4: Partition Files By Process Date

Files are partitioned by the complaint `date_received` value processed by each
DAG run.

Reasoning:

- The CFPB API supports filtering by `date_received_min` and `date_received_max`.
- Airflow runs map cleanly to one date of source data.
- Backfills and catchup runs can be inspected by date in MinIO.
- Reprocessing a date is straightforward because all files for that date share one
  prefix.

Trade-off:

- The current layout uses `YYYY-MM-DD` folders instead of Hive-style folders such as
  `date_received=YYYY-MM-DD`. Hive-style partitions would be easier for some query
  engines to discover automatically.

## Decision 5: Use JSONL For Raw And Parquet For Bronze

Raw data is written as JSONL because it is simple and close to the API response.
Each record is stored as one JSON object per line.

Bronze data is written as Parquet because it is typed, compressed, and efficient for
analytical scans.

Reasoning:

- JSONL is easy to inspect and append chunk by chunk.
- Parquet reduces storage size and improves DuckDB read performance.
- PyArrow can normalize JSONL into a fixed schema before writing Parquet.

## Decision 6: Add `extracted_at` During Ingestion

Each extracted complaint is enriched with an `extracted_at` timestamp.

Reasoning:

- The source API does not provide a pipeline extraction timestamp.
- The field helps distinguish when this local pipeline observed a record.
- It supports debugging repeated runs and late-arriving source changes.

Trade-off:

- `extracted_at` is pipeline metadata, not a CFPB business timestamp.

## Decision 7: Normalize Bronze Data To A Fixed PyArrow Schema

The bronze step casts incoming data to `CFPB_SCHEMA` and fills missing columns with
typed nulls.

Reasoning:

- API responses can omit optional fields.
- DuckDB loads are more stable when every Parquet file has the same columns and
  compatible types.
- Schema drift is handled before data reaches the warehouse table.

Trade-off:

- New CFPB fields will not automatically appear downstream until the schema is
  updated.

## Decision 8: Upsert Into DuckDB By `complaint_id`

DuckDB stores the warehouse source table at:

```text
raw.cfpb_complaints
```

The table uses `complaint_id` as the primary key, and loads use:

```sql
INSERT OR REPLACE
```

Reasoning:

- `complaint_id` is the natural business key for a CFPB complaint.
- Rerunning the same Airflow date should not duplicate records.
- Airflow catchup and backfill runs can safely reload overlapping records.
- If a complaint record changes and is extracted again, the newer version replaces
  the older version.

Trade-off:

- This only handles updates for records that are re-extracted by the pipeline.

## Decision 9: Use Daily Airflow Runs

The DAG runs daily and processes the previous logical date.

Reasoning:

- CFPB data is generally updated daily.
- A daily schedule keeps extraction volume manageable.
- Airflow catchup can create one run per missing date.
- Backfills can target historical ranges through Airflow.

Current behavior:

```text
Airflow logical date -> process logical date minus one day
```

The DAG order is:

```text
extract_complaints_to_raw
  -> load_raw_to_bronze
  -> save_bronze_to_duckdb
  -> dbt run
  -> dbt test
```

## Decision 10: Keep Transformations In dbt

Python handles extraction and loading. dbt handles analytical modeling.

Reasoning:

- dbt models are easier to test, document, and review than embedded SQL strings.
- The project can separate source cleanup, business logic, and marts.
- The dashboard can depend on stable mart tables instead of raw complaint records.

Current dbt model layers:

- `staging`: light cleanup over `raw.cfpb_complaints`.
- `intermediate`: reusable complaint metrics.
- `marts`: fact table, dimensions, and monthly aggregates.

## Decision 11: Keep Dashboard Reads Against Marts

The Streamlit app reads from dbt mart tables instead of directly from raw data.

Reasoning:

- Dashboard queries stay simpler.
- Business definitions live in dbt rather than in the app.
- The app can focus on presentation and interaction.

## Current Limitation: Mutable Source Records

CFPB complaint records can change after their original `date_received`. For example,
a complaint narrative may become available later or be removed later.

The CFPB API does not expose a reliable `updated_at` or `last_modified` field for a
true CDC-style incremental pipeline.

Current implemented approach:

- Each daily DAG run extracts one `date_received`.
- DuckDB upserts by `complaint_id`.
- Reruns, catchups, and backfills are idempotent for the dates they process.

Limitation:

- If a record from an old `date_received` changes and that date is never reprocessed,
  the local warehouse will not see that update.

## Deferred Improvement: Sliding Window Re-Ingestion

A stronger incremental design would reprocess a rolling lookback window.

Example:

```text
Every daily run:
  extract complaints where date_received >= today - 90 days
  write raw and bronze files by date
  upsert records into DuckDB by complaint_id
```

Why this would help:

- Captures many late source changes without needing CDC metadata.
- Keeps the logic simple.
- Works with the existing `complaint_id` upsert design.

Reason it is deferred:

- The current project focuses on a clear daily ingestion path first.
- Sliding-window ingestion requires additional decisions about overwrite behavior,
  duplicate raw files, and how to organize multiple re-extractions of the same date.

## Summary

The pipeline favors clarity, replayability, and local reproducibility over the
shortest possible implementation. Raw JSONL preserves extracted source data, bronze
Parquet provides stable typed files, DuckDB gives a local analytical warehouse, dbt
keeps transformations maintainable, and Airflow coordinates daily operation.
