#!/bin/bash
set -e

# Create temporary container to initialize the volume permissions
echo "Creating temporary container to initialize Synapse volume..."
docker run --rm \
  -v nexus-back_synapse_data:/data \
  --user root \
  --entrypoint /bin/sh \
  matrixdotorg/synapse:latest \
  -c "chown -R 991:991 /data && chmod -R 0700 /data && echo 'Synapse volume permissions set correctly.'"

echo "Synapse data volume initialized successfully."
