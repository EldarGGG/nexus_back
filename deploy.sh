#!/bin/bash

# Nexus Production Deployment Script
# This script handles the complete setup and deployment of the Nexus platform

set -e

echo "🚀 Starting Nexus Production Deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if required files exist
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    required_files=(
        ".env.production"
        "docker-compose.prod.yml"
        "nginx/nginx.conf"
        "matrix/synapse/homeserver.yaml"
        "matrix/element/config.json"
        "init.sql"
    )
    
    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            print_error "Required file missing: $file"
            exit 1
        fi
    done
    
    # Check bridge configs
    bridge_platforms=("whatsapp" "telegram" "instagram" "facebook" "signal")
    for platform in "${bridge_platforms[@]}"; do
        if [ ! -f "matrix/bridges/$platform/config.yaml" ]; then
            print_error "Bridge config missing: matrix/bridges/$platform/config.yaml"
            exit 1
        fi
    done
    
    print_success "All prerequisite files found"
}

# Generate secure secrets
generate_secrets() {
    print_status "Generating secure secrets..."
    
    if [ ! -f ".env.production" ]; then
        print_error ".env.production file not found"
        exit 1
    fi
    
    # Generate Django secret key if not set
    if ! grep -q "DJANGO_SECRET_KEY=" .env.production || grep -q "your-super-secret-key-change-in-production" .env.production; then
        DJANGO_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')
        sed -i.bak "s/DJANGO_SECRET_KEY=.*/DJANGO_SECRET_KEY=$DJANGO_SECRET/" .env.production
        print_success "Generated Django secret key"
    fi
    
    # Generate encryption key if not set
    if ! grep -q "NEXUS_ENCRYPTION_KEY=" .env.production || grep -q "your-encryption-key-32-chars-long" .env.production; then
        ENCRYPTION_KEY=$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')
        sed -i.bak "s/NEXUS_ENCRYPTION_KEY=.*/NEXUS_ENCRYPTION_KEY=$ENCRYPTION_KEY/" .env.production
        print_success "Generated encryption key"
    fi
    
    # Generate Matrix registration shared secret if not set
    if ! grep -q "SYNAPSE_REGISTRATION_SHARED_SECRET=" .env.production; then
        MATRIX_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
        echo "SYNAPSE_REGISTRATION_SHARED_SECRET=$MATRIX_SECRET" >> .env.production
        print_success "Generated Matrix registration secret"
    fi
    
    print_success "Secrets generation completed"
}

# Prepare directories
prepare_directories() {
    print_status "Preparing directories..."
    
    directories=(
        "logs"
        "media"
        "static"
        "postgres_data"
        "synapse_data"
        "matrix/bridges/whatsapp/logs"
        "matrix/bridges/telegram/logs"
        "matrix/bridges/instagram/logs"
        "matrix/bridges/facebook/logs"
        "matrix/bridges/signal/logs"
    )
    
    for dir in "${directories[@]}"; do
        mkdir -p "$dir"
        print_success "Created directory: $dir"
    done
    
    # Set proper permissions
    chmod -R 755 logs media static
    chmod -R 700 postgres_data synapse_data
    
    print_success "Directory preparation completed"
}

# Start database first
start_database() {
    print_status "Starting PostgreSQL database..."
    
    docker-compose -f docker-compose.prod.yml up -d postgres
    
    # Wait for database to be ready
    print_status "Waiting for database to be ready..."
    for i in {1..30}; do
        if docker-compose -f docker-compose.prod.yml exec -T postgres pg_isready -U nexus_user -d nexus_db; then
            print_success "Database is ready"
            return 0
        fi
        sleep 2
    done
    
    print_error "Database failed to start within 60 seconds"
    exit 1
}

# Run Django migrations
run_migrations() {
    print_status "Running Django migrations..."
    
    docker-compose -f docker-compose.prod.yml run --rm web python manage.py migrate
    
    print_success "Django migrations completed"
}

# Create Django superuser
create_superuser() {
    print_status "Creating Django superuser..."
    
    if [ -z "$DJANGO_SUPERUSER_PASSWORD" ]; then
        print_warning "DJANGO_SUPERUSER_PASSWORD not set in environment"
        read -s -p "Enter superuser password: " DJANGO_SUPERUSER_PASSWORD
        echo
    fi
    
    docker-compose -f docker-compose.prod.yml run --rm web python manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@nexus.local', '$DJANGO_SUPERUSER_PASSWORD')
    print('Superuser created successfully')
else:
    print('Superuser already exists')
EOF
    
    print_success "Superuser setup completed"
}

# Start core services
start_core_services() {
    print_status "Starting core services (Synapse, Element, Web)..."
    
    docker-compose -f docker-compose.prod.yml up -d synapse element web nginx
    
    # Wait for services to be ready
    print_status "Waiting for core services to be ready..."
    sleep 30
    
    # Check if services are responding
    if curl -s http://localhost/health/ > /dev/null; then
        print_success "Core services are running"
    else
        print_warning "Core services may need more time to start"
    fi
}

# Start bridge services
start_bridge_services() {
    print_status "Starting bridge services..."
    
    # Start bridges one by one to avoid overwhelming the system
    bridges=("whatsapp-bridge" "telegram-bridge" "instagram-bridge" "facebook-bridge" "signal-bridge")
    
    for bridge in "${bridges[@]}"; do
        print_status "Starting $bridge..."
        docker-compose -f docker-compose.prod.yml up -d "$bridge"
        sleep 10
    done
    
    print_success "Bridge services started"
}

# Verify deployment
verify_deployment() {
    print_status "Verifying deployment..."
    
    # Check if all containers are running
    running_containers=$(docker-compose -f docker-compose.prod.yml ps --services --filter "status=running" | wc -l)
    total_containers=$(docker-compose -f docker-compose.prod.yml ps --services | wc -l)
    
    if [ "$running_containers" -eq "$total_containers" ]; then
        print_success "All containers are running ($running_containers/$total_containers)"
    else
        print_warning "Some containers may not be running ($running_containers/$total_containers)"
    fi
    
    # Check API health
    if curl -s http://localhost/api/health/ | grep -q "ok"; then
        print_success "API is responding"
    else
        print_warning "API health check failed"
    fi
    
    # Check Element access
    if curl -s http://localhost/ | grep -q "Element"; then
        print_success "Element is accessible"
    else
        print_warning "Element access check failed"
    fi
}

# Display final information
display_info() {
    echo
    echo "🎉 Nexus deployment completed!"
    echo
    echo "📋 Service Information:"
    echo "   Web Application: http://localhost/"
    echo "   Element Client:  http://localhost/"
    echo "   Admin Panel:     http://localhost/admin/"
    echo "   API Docs:        http://localhost/api/"
    echo
    echo "🔐 Default Credentials:"
    echo "   Admin Username:  admin"
    echo "   Admin Password:  [as configured]"
    echo
    echo "📖 Documentation:"
    echo "   Setup Guide:     ./BRIDGE_SETUP_GUIDE.md"
    echo "   Integration:     ./FRONTEND_BACKEND_INTEGRATION.md"
    echo "   README:          ./README.md"
    echo
    echo "🛠️  Useful Commands:"
    echo "   View logs:       docker-compose -f docker-compose.prod.yml logs -f [service]"
    echo "   Stop all:        docker-compose -f docker-compose.prod.yml down"
    echo "   Restart:         docker-compose -f docker-compose.prod.yml restart [service]"
    echo
}

# Main deployment flow
main() {
    echo "🏢 Nexus B2B AI SaaS Messaging Platform"
    echo "==============================================="
    echo
    
    check_prerequisites
    generate_secrets
    prepare_directories
    start_database
    run_migrations
    create_superuser
    start_core_services
    start_bridge_services
    verify_deployment
    display_info
}

# Handle script arguments
case "${1:-}" in
    "check")
        check_prerequisites
        ;;
    "secrets")
        generate_secrets
        ;;
    "dirs")
        prepare_directories
        ;;
    "db")
        start_database
        ;;
    "migrate")
        run_migrations
        ;;
    "superuser")
        create_superuser
        ;;
    "core")
        start_core_services
        ;;
    "bridges")
        start_bridge_services
        ;;
    "verify")
        verify_deployment
        ;;
    "info")
        display_info
        ;;
    "")
        main
        ;;
    *)
        echo "Usage: $0 [check|secrets|dirs|db|migrate|superuser|core|bridges|verify|info]"
        echo "       $0           # Run full deployment"
        exit 1
        ;;
esac
