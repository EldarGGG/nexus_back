#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Function to wait for database
wait_for_db() {
    echo "Waiting for database..."
    while ! nc -z db 5432; do
        echo "Database is unavailable - sleeping"
        sleep 1
    done
    echo "Database is up!"
}

# Function to wait for Redis
wait_for_redis() {
    echo "Waiting for Redis..."
    while ! nc -z redis 6379; do
        echo "Redis is unavailable - sleeping"
        sleep 1
    done
    echo "Redis is up!"
}

# Only run migrations and setup if this is the web service
if [ "$1" = "daphne" ]; then
    # Wait for services
    wait_for_db
    wait_for_redis

    # Run database migrations
    echo "Running database migrations..."
    python manage.py makemigrations --noinput
    python manage.py migrate --noinput

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
