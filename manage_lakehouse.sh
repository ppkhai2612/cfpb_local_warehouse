#!/bin/bash

set -e

# Get the absolute path of the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Function to start all services
start_services() {
    echo "Starting CFPB Local Lakehouse services..."
    cd "$SCRIPT_DIR"

    # Step 1: Start the data lake infrastructure (MinIO + Nessie)
    echo "Starting data lake services (MinIO + Nessie)..."
    docker compose -f docker-compose-lake.yml up -d
    sleep 30

    # Step 2: Start Trino query engine
    echo "Starting Trino query engine..."
    docker compose -f docker-compose-trino.yml up -d
    sleep 30

    # Step 3: Start Airflow
    ./run_airflow.sh &
    sleep 30

    echo "All services started successfully."
    echo ""
    echo "Service Access Information:"
    echo "  - MinIO Console: http://localhost:9001 (minio/minio123)"
    echo "  - Trino UI: http://localhost:8080"
    echo "  - Airflow UI: http://localhost:8081 (airflow/airflow)"
    echo "  - Nessie API: http://localhost:19120"
    echo ""
}

# Function to stop all services and clean up resources
stop_services() {
    echo "Stopping CFPB Local Lakehouse services..."
    cd "$SCRIPT_DIR"
    
    # Stop services in reverse order (Airflow -> Trino -> Lake)
    # echo "Stopping Airflow..."
    # docker compose -f docker-compose-airflow.yaml down -v
    
    echo "Stopping Trino..."
    docker compose -f docker-compose-trino.yml down -v
    
    echo "Stopping data lake services (MinIO + Nessie)..."
    docker compose -f docker-compose-lake.yaml down -v
    
    echo "All services stopped and volumes cleaned up."
}

# # 1. Create .env file if it doesn't exist
# if [[ ! -f .env ]]; then
#     echo ".env file not found. Copying from .env.example..."
#     cp .env.example .env
# fi

# # 2. Create .venv file if it doesn't exist
# if [[ -d .venv ]]; then
#     echo "Setting up Python virtual environment..."
#     make setup
# fi

# # 3. Start infrastructure
# echo "Starting Docker containers..."
# make up

# # Waiting for the services to be ready
# echo "Waiting for the services to be ready. (about 30s)"
# sleep 30

# # 4. Run pipeline
# echo "Running pipeline..."
# make run-pipeline

# # 5. Run dbt transformations
# echo "Running dbt transformations..."
# make dbt-run

# # 6. See results
# echo "Project is up and running"
# echo "MinIO Console: http://localhost:9001"



# main script logic - handle command line arguments
case "${1:-help}" in
    "start")
        start_services
        ;;
    "stop")
        stop_services
        ;;
    *)
        echo "Usage: $0 [start|stop]"
        echo "Script for CFPB Local Lakehouse management"
        echo ""
        echo "Commands:"
        echo "    start   Start all lakehouse services (MinIO, Nessie, Trino, Airflow)"
        echo "    stop    Stop all services (volumes also cleaned up)"
        echo ""
        echo "Examples:"
        echo " $0 start    # Start the whole lakehouse stack"
        echo " $0 stop     # Stop all services and clean up"
        echo "After starting, you can access:"
        echo "  - MinIO Console: http://localhost:9001"
        echo "  - Airflow UI: http://localhost:8081"
        echo "  - Trino Web UI: http://localhost:8080" 
        ;;
esac