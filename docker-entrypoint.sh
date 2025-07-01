#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Function to wait for database using DATABASE_URL or direct host/port
wait_for_db() {
    echo "Waiting for database..."
    
    if [ -n "$DATABASE_URL" ]; then
        # Extract host and port from DATABASE_URL
        # Example format: postgres://user:pass@host:port/db
        DB_HOST=$(echo $DATABASE_URL | sed -e 's/^.*@//g' -e 's/:[0-9]*.*$//g')
        DB_PORT=$(echo $DATABASE_URL | sed -e 's/^.*://g' -e 's/\/.*$//g')
        
        echo "Connecting to database at $DB_HOST:$DB_PORT"
        while ! nc -z $DB_HOST $DB_PORT; do
            echo "Database is unavailable - sleeping"
            sleep 1
        done
    elif [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ]; then
        echo "Connecting to database at $DB_HOST:$DB_PORT"
        while ! nc -z $DB_HOST $DB_PORT; do
            echo "Database is unavailable - sleeping"
            sleep 1
        done
    else
        echo "DATABASE_URL or DB_HOST/DB_PORT not provided, skipping database wait"
    fi
    
    echo "Database connection established or skipped!"
}

# Function to wait for Redis using REDIS_URL or direct host/port
wait_for_redis() {
    echo "Waiting for Redis..."
    
    if [ -n "$REDIS_URL" ]; then
        # Extract host and port from REDIS_URL
        # Example format: redis://user:pass@host:port
        REDIS_HOST=$(echo $REDIS_URL | sed -e 's/^.*@//g' -e 's/:[0-9]*.*$//g')
        REDIS_PORT=$(echo $REDIS_URL | sed -e 's/^.*://g' -e 's/\/.*$//g')
        
        echo "Connecting to Redis at $REDIS_HOST:$REDIS_PORT"
        while ! nc -z $REDIS_HOST $REDIS_PORT; do
            echo "Redis is unavailable - sleeping"
            sleep 1
        done
    elif [ -n "$REDIS_HOST" ] && [ -n "$REDIS_PORT" ]; then
        echo "Connecting to Redis at $REDIS_HOST:$REDIS_PORT"
        while ! nc -z $REDIS_HOST $REDIS_PORT; do
            echo "Redis is unavailable - sleeping"
            sleep 1
        done
    else
        echo "REDIS_URL or REDIS_HOST/REDIS_PORT not provided, skipping Redis wait"
    fi
    
    echo "Redis connection established or skipped!"
}

# Set up proper error handling
set -o pipefail

# Show all executed commands for debugging
if [ "$DEBUG" = "True" ]; then
    set -x
fi

# Print env variables for debugging (excluding sensitive data)
echo "Environment variables (non-sensitive):"
env | grep -v "SECRET\|PASSWORD\|KEY" || true

# Only run migrations and setup if this is the web service
if [[ "$1" = "daphne" ]] || [[ "$@" == *"daphne"* ]]; then
    echo "Starting web service preparation..."
    # Wait for services
    wait_for_db || echo "Warning: Database connection failed or skipped"
    wait_for_redis || echo "Warning: Redis connection failed or skipped"

    # Ensure directory structure
    mkdir -p /app/static /app/media /app/logs

    # Collect static files
    echo "Collecting static files..."
    python manage.py collectstatic --noinput || echo "Static file collection failed, but continuing"
    
    # Run database migrations
    echo "Running database migrations..."
    python manage.py makemigrations --noinput || echo "Makemigrations failed, but continuing"
    python manage.py migrate --noinput || echo "Migration failed, but continuing"

    # Create superuser if it doesn't exist
    echo "Creating superuser..."
    python manage.py shell << 'EOF'
import os
import django
django.setup()

from authentication.models import CustomUser
from companies.models import Company

if not CustomUser.objects.filter(username='admin').exists():
    # Create default company
    company, created = Company.objects.get_or_create(
        name='Nexus Admin',
        defaults={
            'industry': 'technology',
            'company_size': '1-10',
            'slug': 'nexus-admin'
        }
    )
    
    # Create superuser
    user = CustomUser.objects.create_superuser(
        username='admin',
        email='admin@nexus.com',
        password='admin123',
        company=company
    )
    print('Superuser created successfully')
else:
    print('Superuser already exists')
EOF

    # Collect static files
    echo "Collecting static files..."
    python manage.py collectstatic --noinput

    echo "Setup completed successfully!"
fi

# Start the application
echo "Starting application..."
exec "$@"
