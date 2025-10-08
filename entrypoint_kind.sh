#!/bin/bash
set -euo pipefail

DATA_DIR="/home/appuser/app/data"

# ==============================
# Cleanup handling
# ==============================
cleanup() {
    echo "🛑 Cleaning up background processes..."
    [ -n "${MCP_PID:-}" ] && kill "$MCP_PID" 2>/dev/null || true
    [ -n "${STREAMLIT_PID:-}" ] && kill "$STREAMLIT_PID" 2>/dev/null || true
    exit 1
}
trap cleanup SIGINT SIGTERM ERR

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
# Prepare kubeconfig
# ==============================
KUBE_DIR_WRITABLE="$HOME/.kube-writable"
mkdir -p "$KUBE_DIR_WRITABLE"

if [ -f "$HOME/.kube/config" ]; then
  echo "[KUBECONFIG] Copying from $HOME/.kube/config"
  cp "$HOME/.kube/config" "$KUBE_DIR_WRITABLE/config"
elif [ -f "/root/.kube/config" ]; then
  echo "[KUBECONFIG] Copying from /root/.kube/config"
  cp "/root/.kube/config" "$KUBE_DIR_WRITABLE/config"
else
  echo "[KUBECONFIG] ❌ No kubeconfig found!"
  exit 1
fi

export KUBECONFIG="$KUBE_DIR_WRITABLE/config"

echo "[KUBECONFIG] First 10 lines before patch:"
head -n 10 "$KUBECONFIG" || true

# ==============================
# Patch kubeconfig
# ==============================
CONTROL_PLANE_IP="${CONTROL_PLANE_IP:-127.0.0.1}"
CONTROL_PLANE_PORT="${CONTROL_PLANE_PORT:-6443}"
echo "[KUBECONFIG] Using control-plane: $CONTROL_PLANE_IP:$CONTROL_PLANE_PORT"

# Replace only cluster.server line
sed -i "s#\(server: https://\)[^:]\+:[0-9]\+#\1$CONTROL_PLANE_IP:$CONTROL_PLANE_PORT#g" "$KUBECONFIG"

echo "[KUBECONFIG] First 10 lines after patch:"
head -n 10 "$KUBECONFIG" || true

# ==============================
# Start MCP server
# ==============================
echo "[MCP] Starting MCP server..."
# KUBECONFIG="$KUBECONFIG" python k8_mcp_server.py > /var/log/mcp.log 2>&1 &
KUBECONFIG="$KUBECONFIG" python k8_mcp_server.py &

MCP_PID=$!
echo "[MCP] PID: $MCP_PID"

# Wait for MCP health with timeout
echo "[MCP] Waiting for MCP server health..."
for i in {1..30}; do
   if curl -fs http://localhost:8001/health >/dev/null; then
      echo "[MCP] ✅ Ready!"
      break
   fi
   echo "[MCP] ⏱ Still waiting..."
   sleep 1
done

if ! curl -fs http://localhost:8001/health >/dev/null; then
    echo "[MCP] ❌ MCP server failed to start within timeout"
    cleanup
fi

# ==============================
# Start Streamlit
# ==============================
echo "[STREAMLIT] Starting UI..."
streamlit run web_app_kind.py \
  --server.address=0.0.0.0 \
  --server.port=8501 \
  --server.headless=true &
STREAMLIT_PID=$!

# ==============================
# Monitor processes
# ==============================
wait -n $MCP_PID $STREAMLIT_PID
echo "[SYSTEM] ⚠️ One process exited unexpectedly. Cleaning up..."
cleanup
