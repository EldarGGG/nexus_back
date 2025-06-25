#!/bin/bash

# Synapse initialization script
SYNAPSE_DATA_DIR="/data"
CONFIG_FILE="$SYNAPSE_DATA_DIR/homeserver.yaml"

# If no config file exists, generate it
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Generating initial Synapse configuration..."
    
    # Generate the config
    /usr/local/bin/python -m synapse.app.homeserver \
        --server-name matrix.nexus.local \
        --config-path $CONFIG_FILE \
        --generate-config \
        --report-stats=no
    
    # Set ownership to synapse user
    chown -R 991:991 $SYNAPSE_DATA_DIR
fi

# Replace with our custom configuration if it exists
if [ -f "/tmp/custom-homeserver.yaml" ]; then
    echo "Applying custom configuration..."
    cp /tmp/custom-homeserver.yaml $CONFIG_FILE
    chown 991:991 $CONFIG_FILE
fi

if [ -f "/tmp/custom-log-config.yaml" ]; then
    echo "Applying custom log configuration..."
    cp /tmp/custom-log-config.yaml $SYNAPSE_DATA_DIR/matrix.nexus.local.log.config
    chown 991:991 $SYNAPSE_DATA_DIR/matrix.nexus.local.log.config
fi

# Ensure correct ownership
chown -R 991:991 $SYNAPSE_DATA_DIR

# Start Synapse
echo "Starting Synapse..."
exec /usr/local/bin/python -m synapse.app.homeserver --config-path $CONFIG_FILE
