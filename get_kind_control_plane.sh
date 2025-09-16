#!/bin/bash
set -euo pipefail

# Get the first Kind control-plane container
CONTROL_PLANE_CONTAINER=$(docker ps --filter "name=control-plane" --format "{{.Names}}" | head -n 1)

if [ -z "$CONTROL_PLANE_CONTAINER" ]; then
    echo "❌ Could not find a Kind control-plane container."
    exit 1
fi

# Get its IP inside the Docker network
CONTROL_PLANE_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$CONTROL_PLANE_CONTAINER")

# Default Kubernetes API server port for Kind
CONTROL_PLANE_PORT=6443

# Output in KEY=VALUE format
echo "CONTROL_PLANE_IP=$CONTROL_PLANE_IP"
echo "CONTROL_PLANE_PORT=$CONTROL_PLANE_PORT"
