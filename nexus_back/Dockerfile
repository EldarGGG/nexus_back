# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DJANGO_SETTINGS_MODULE=nexus_back.settings

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libssl-dev \
        libffi-dev \
        libjpeg-dev \
        libpng-dev \
        libwebp-dev \
        zlib1g-dev \
        gcc \
        g++ \
        curl \
        git \
        pkg-config \
        redis-tools \
        postgresql-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install wheel
RUN pip install --upgrade pip setuptools wheel

# Copy requirements first for better Docker layer caching
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . /app/

# Create directories for media and static files
RUN mkdir -p /app/media /app/static /app/logs

# Create non-root user for security
RUN groupadd -r nexus && useradd -r -g nexus nexus

# Set proper permissions
RUN chown -R nexus:nexus /app

# Switch to non-root user
USER nexus

# Collect static files
RUN python manage.py collectstatic --noinput --clear

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Default command
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "nexus_back.asgi:application"]