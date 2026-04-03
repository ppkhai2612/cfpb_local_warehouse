# Airflow Documentation

## 1. Overview

**Apache Airflow** is an open-source platform for developing, scheduling, and monitoring batch-oriented workflows. Airflow workflows are defined entirely in Python code with Dags and Tasks

### Dag and Task

**A Dag** is a model that encapsulates everything needed to execute a workflow. You can add Dag attributes as Dag configuration. While **task** is the basic unit of execution in Airflow. Multiple tasks are arranged into a Dag

```python
from datetime import datetime

from airflow.sdk import DAG, task
from airflow.providers.standard.operators.bash import BashOperator

# A Dag represents a workflow, a collection of tasks
with DAG(dag_id="demo", start_date=datetime(2022, 1, 1), schedule="0 0 * * *") as dag:
    # Tasks are represented as operators
    hello = BashOperator(task_id="hello", bash_command="echo hello")

    @task()
    def airflow():
        print("airflow")

    # Set dependencies between tasks
    hello >> airflow()
```

Explaination

- A Dag named `demo`, scheduled to run daily starting on January 1st, 2022
- Two tasks: One using a `BashOperator` to run a shell script, and another using the `@task` decorator to define a Python function
- The `>>` operator defines a dependency betweentwo tasks and controls execution order

## 2. Deployment

In this project, Airflow is deployed in Docker. I followed to [this guide](https://airflow.apache.org/docs/apache-airflow/3.0.6/howto/docker-compose/index.html) but replaced `CeleryExecutor` with `LocalExecutor`. Airflow containers included

- `postgres` - The metadata database stores the state of Dags, Tasks, and Variables
- `airflow-scheduler` - The scheduler monitors all Dags and Tasks, then triggers the task instances once their dependencies are complete
- `airflow-dag-processor` - The Dag processor parses Dag files
- `airflow-api-server` - The api server presents a handy user interface to inspect, trigger and debug the behaviour of Dags and tasks. It is available at http://localhost:8080
- `airflow-init` - The initialization service

### Understanding the details of services

**Postgres**

- Docker Image: [postgres](https://hub.docker.com/_/postgres)
- Environment Variables
    - `POSTGRES_PASSWORD` and `POSTGRES_USER`: sets the superuser for PostgreSQL
    - `POSTGRES_DB`: specify a name for the default database that is created when the image is first started

**Airflow init**

Entrypoint in Airflow init will perform the following actions
- Setting the right user for Airflow through `AIRFLOW_UID`
- Check if system has enough resources to run Airflow
- Creating the necessary directories if they don't already exist (these dirs are mounted to host's filesystem)
- Creating the default config file if missing (`config/airflow.cfg`)
- Changing ownership of dirs/files to avoid permission errors in Airflow
- Migrate the schema of the metadata database. Create the database if it does not exist (`_AIRFLOW_DB_MIGRATE`)
- Creating webserver user automatically (`_AIRFLOW_WWW_USER_CREATE`)

**Airflow scheduler**

Start a scheduler instance when container is run
- Once per minute, by default, the scheduler collects Dag parsing results and checks whether any active tasks can be triggered (`scheduler.parsing_cleanup_interval`)
- The scheduler runs AFTER the `start_date`, at the END of the interval (for Dags with a cron or timedelta schedule). For example, if you run a Dag on a schedule of one day, the run with data interval starting on 2019-11-21 triggers after 2019-11-21T23:59

**Airflow API server**

- Start a api server instance when container is run
- Airflow Web UI: http://localhost:8080

**Airflow Dag processor**

- Start a dag processor instance when container is run
- Every 5 minutes, the DAG processor scans the `dags` directory to update the latest state of the files (`dag_processor.refresh_interval`)
