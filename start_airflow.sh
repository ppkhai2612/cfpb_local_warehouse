#!/bin/bash

set -e

source .env # 

# always get absolute path of the dir where the script is run
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

# Ensure using the Airflow is installed from the project's .venv
VENV_BIN="${REPO_ROOT}/.venv/bin"

if [[ ! -f "${VENV_BIN}/airflow" ]]; then
    echo "ERROR: Airflow not found in .venv." >&2
    echo "       From the project root, run:" >&2
    echo "         uv sync" >&2
    echo "" >&2
    echo "       Then re-run ./start_airflow.sh. (Don't use bare 'pip install' -" >&2
    echo "       it can resolve to a pyenv shim and install into the wrong" >&2
    echo "       environment. uv sync always target this project's .venv." >&2
    exit 1
fi

# Prepend .venv/bin to PATH, so all standalone's subprocesses (scheduler, api-server,...) are resolved
export PATH="${VENV_BIN}:${PATH}"

# Airflow configurations
export AIRFLOW_HOME="${REPO_ROOT}/airflow"
export AIRFLOW__CORE__DAGS_FOLDER="${AIRFLOW_HOME}/dags"
export AIRFLOW__CORE__LOAD_EXAMPLES=False
export AIRFLOW__CORE__EXECUTION_API_SERVER_URL="http://localhost:8081/execution/"
export AIRFLOW__API__PORT=8081

# Simple Auth Manager
PASSWORD_FILE="${AIRFLOW_HOME}/simple_auth_manager_passwords.json.generated"
mkdir -p "${AIRFLOW_HOME}"
if [[ ! -f "${PASSWORD_FILE}" ]]; then
    # echo '{${AIRFLOW_USERNAME}": "khai2612"}' > "${PASSWORD_FILE}"
    echo "{\"${AIRFLOW_USERNAME}\": \"${AIRFLOW_PASSWORD}\"}" > "${PASSWORD_FILE}"
fi

# if this config not set, Airflow ignores "airflow" user and creates a new "admin" user 
export AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_USERS="${AIRFLOW_USERNAME}:admin"

# Show some informations
echo " Starting Airflow standalone..."
echo "   AIRFLOW_HOME        = ${AIRFLOW_HOME}"
echo "   DAGS_FOLDER         = ${AIRFLOW__CORE__DAGS_FOLDER}"
echo "   UI                  = http://localhost:8081"
echo "   Credentials         = ${AIRFLOW_USERNAME} / ${AIRFLOW_PASSWORD}"
echo ""
echo "   To stop: Ctrl+C"
echo ""

# Start Airflow
airflow standalone