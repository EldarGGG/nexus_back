#!/bin/bash

# Exit on error
set -e

echo "=== Starting Nexus Backend ==="

# Navigate to Django project directory
cd nexus_back

# Set up Python path
export PYTHONPATH=$(pwd)

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Apply database migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Start Daphne server
echo "Starting Daphne ASGI server..."
daphne -b 0.0.0.0 -p $PORT nexus_back.asgi:application
