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

# ==============================
# Determine container type
# ==============================
# Must be set in docker-compose environment
CONTAINER_TYPE="${CONTAINER_TYPE:-k8s}"  # default k8s

if [[ "$CONTAINER_TYPE" == "k8s" ]]; then
    # ------------------------------
    # Kubernetes MCP container
    # ------------------------------
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

    echo "[KUBECONFIG] First 10 lines before patch:"
    head -n 10 "$KUBECONFIG" || true

    CONTROL_PLANE_IP="${CONTROL_PLANE_IP:-127.0.0.1}"
    CONTROL_PLANE_PORT="${CONTROL_PLANE_PORT:-6443}"

    sed -i "s#\(server: https://\)[^:]\+:[0-9]\+#\1$CONTROL_PLANE_IP:$CONTROL_PLANE_PORT#g" "$KUBECONFIG"

    echo "[KUBECONFIG] First 10 lines after patch:"
    head -n 10 "$KUBECONFIG" || true

    echo "[MCP] Starting Kubernetes MCP server..."
    python k8_mcp_server.py &

    MCP_PID=$!
    # Wait for health
    for i in {1..30}; do
        if curl -fs http://localhost:8001/health >/dev/null; then
            echo "[MCP] ✅ Ready!"
            break
        fi
        echo "[MCP] ⏱ Still waiting..."
        sleep 1
    done

    if ! curl -fs http://localhost:8001/health >/dev/null; then
        echo "[MCP] ❌ MCP server failed to start"
        exit 1
    fi

    echo "[STREAMLIT] Starting UI..."
    streamlit run web_app.py \
        --server.address=0.0.0.0 \
        --server.port=8501 \
        --server.headless=true &
    STREAMLIT_PID=$!

    wait -n $MCP_PID $STREAMLIT_PID

else
    # ------------------------------
    # S3 MCP container
    # ------------------------------
    echo "[S3] Starting S3 Health Server + MCP..."
    python s3_mcp_server.py &
    wait
fi
