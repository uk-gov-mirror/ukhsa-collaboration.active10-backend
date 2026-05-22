#!/bin/bash

set -e

echo "Waiting for Postgresql to be ready..."
while ! nc -z $DB_HOST $DB_PORT; do
  sleep 1
done

echo "Running database migrations..."
alembic upgrade head

# echo "Running activities partitioning script..."
# python scripts/activities_partitioning.py

echo "Starting FastAPI application..."

if [ "$DEBUG" = "True" ]; then
  echo "Running in debug mode. Do not use this in production!"
  RELOAD_FLAG="--reload"
fi

uvicorn main:app --host 0.0.0.0 --port 8000 $RELOAD_FLAG