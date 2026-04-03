# Local Lakehouse Pipeline for Complaint Data

This project implements a **local pipeline** that retrieves consumer **complaint data** from the CFPB API, this data, then, is stored in a **data lakehouse** (MinIO + Iceberg). The data in the lakehouse can be in raw format for auditing or transformed to serve business use cases such as advanced analytics, reporting, etc

## Data Stacks

1. **MinIO** for object storage
2. **Iceberg** for open table format
3. **Nessie** for Iceberg catalog
4. **dbt** for transformation logic
5. **Spark** for ingestion & compute engine
6. **Airflow** for orchestration
7. **Docker** for containerization

## Architecture

## Quick Start

To start up the pipeline, run `./manage-lakehouse.sh start`
