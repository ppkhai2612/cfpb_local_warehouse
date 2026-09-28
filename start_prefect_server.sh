#!/bin/bash
# Start Prefect server for the local ELT pipeline

echo "Starting Prefect server..."
echo ""
echo "Once started, you can access the Prefect UI at: http://127.0.0.1:4200"
echo "Press Ctrl+C to stop the server"
echo ""

cd "$(dirname "$0")"
uv run prefect server start