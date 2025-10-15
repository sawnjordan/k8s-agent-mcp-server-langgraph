#!/bin/bash
set -euo pipefail

DATA_DIR="/home/appuser/app/data"

# ==============================
# Fix data directory permissions
# ==============================
if [ -d "$DATA_DIR" ]; then
    echo "[SETUP] Fixing permissions for $DATA_DIR..."
    chown -R appuser:appuser "$DATA_DIR"
fi

export PATH="$HOME/.local/bin:$PATH"
echo "[ENV] Running as user: $(whoami)"
echo "[ENV] HOME: $HOME"

CONTAINER_TYPE="${CONTAINER_TYPE:-k8s}"  # default k8s

# ==============================
# Fix kubeconfig for k8s container
# ==============================
if [[ "$CONTAINER_TYPE" == "k8s" ]]; then
    echo "[K8S] Setting up kubeconfig..."
    KUBE_DIR_WRITABLE="$HOME/.kube-writable"
    mkdir -p "$KUBE_DIR_WRITABLE"

    if [ -f "$HOME/.kube/config" ]; then
        cp "$HOME/.kube/config" "$KUBE_DIR_WRITABLE/config"
    elif [ -f "/root/.kube/config" ]; then
        cp "/root/.kube/config" "$KUBE_DIR_WRITABLE/config"
    else
        echo "[KUBECONFIG] ❌ No kubeconfig found!"
        exit 1
    fi

    export KUBECONFIG="$KUBE_DIR_WRITABLE/config"

fi

# ==============================
# Function to wait for service
# ==============================
wait_for_service() {
    local url=$1
    local name=$2
    local retries=${3:-30}
    local wait_sec=${4:-2}

    echo "[WAIT] Waiting for $name at $url..."
    for i in $(seq 1 $retries); do
        if curl -fs "$url" >/dev/null 2>&1; then
            echo "[WAIT] $name is ready!"
            return 0
        fi
        sleep $wait_sec
    done
    echo "[WAIT] ❌ $name failed to become ready"
    exit 1
}

# ==============================
# Start services
# ==============================
if [[ "$CONTAINER_TYPE" == "k8s" ]]; then
    echo "[MCP] Starting Kubernetes MCP server..."
    python k8_mcp_server.py &
    MCP_PID=$!

    wait_for_service http://localhost:8001/health "K8s MCP"

    echo "[STREAMLIT] Starting Streamlit UI..."
    streamlit run web_app.py \
        --server.address=0.0.0.0 \
        --server.port=8501 \
        --server.headless=true &
    STREAMLIT_PID=$!

    wait -n $MCP_PID $STREAMLIT_PID

elif [[ "$CONTAINER_TYPE" == "s3" ]]; then
    echo "[S3] Starting S3 MCP server..."
    python aws_s3_server.py &
    S3_MCP_PID=$!

    wait_for_service http://localhost:8011/health "S3 MCP"

    wait $S3_MCP_PID

fi
