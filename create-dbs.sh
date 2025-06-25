#!/bin/bash
set -e

# Create all required databases
POSTGRES_USERNAME="nexus_user"
POSTGRES_PASSWORD="nexus_password"

echo "Creating synapse_db..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE IF NOT EXISTS synapse_db;
    GRANT ALL PRIVILEGES ON DATABASE synapse_db TO $POSTGRES_USERNAME;
EOSQL

echo "Creating whatsapp_bridge_db..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE whatsapp_bridge_db;
    GRANT ALL PRIVILEGES ON DATABASE whatsapp_bridge_db TO $POSTGRES_USERNAME;
EOSQL

echo "Creating telegram_bridge_db..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE telegram_bridge_db;
    GRANT ALL PRIVILEGES ON DATABASE telegram_bridge_db TO $POSTGRES_USERNAME;
EOSQL

echo "Creating instagram_bridge_db..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE instagram_bridge_db;
    GRANT ALL PRIVILEGES ON DATABASE instagram_bridge_db TO $POSTGRES_USERNAME;
EOSQL

echo "Creating facebook_bridge_db..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE facebook_bridge_db;
    GRANT ALL PRIVILEGES ON DATABASE facebook_bridge_db TO $POSTGRES_USERNAME;
EOSQL

echo "Creating signal_bridge_db..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE signal_bridge_db;
    GRANT ALL PRIVILEGES ON DATABASE signal_bridge_db TO $POSTGRES_USERNAME;
EOSQL

echo "All databases created successfully!"
