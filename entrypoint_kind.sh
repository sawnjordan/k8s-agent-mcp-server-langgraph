#!/bin/bash
set -euo pipefail

DATA_DIR="/home/appuser/app/data"
if [ -d "$DATA_DIR" ]; then
    echo "🔧 Fixing permissions for data directory..."
    chown -R appuser:appuser "$DATA_DIR"
fi

export PATH="$HOME/.local/bin:$PATH"

echo "👤 Running as user: $(whoami)"
echo "📂 HOME: $HOME"

# --- Fix kubeconfig inside container/user environment ---
KUBE_DIR_WRITABLE="$HOME/.kube-writable"
mkdir -p "$KUBE_DIR_WRITABLE"

if [ -f "$HOME/.kube/config" ]; then
  echo "📄 Copying kubeconfig from $HOME/.kube/config"
  cp "$HOME/.kube/config" "$KUBE_DIR_WRITABLE/config"
elif [ -f "/root/.kube/config" ]; then
  echo "📄 Copying kubeconfig from /root/.kube/config"
  cp "/root/.kube/config" "$KUBE_DIR_WRITABLE/config"
else
  echo "❌ No kubeconfig found!"
  exit 1
fi

export KUBECONFIG="$KUBE_DIR_WRITABLE/config"

echo "📄 kubeconfig head (before patch):"
head -n 10 "$KUBECONFIG" || true

# --- Read control-plane IP/port from environment ---
CONTROL_PLANE_IP="${CONTROL_PLANE_IP:-127.0.0.1}"
CONTROL_PLANE_PORT="${CONTROL_PLANE_PORT:-6443}"

echo "🔧 Using control-plane: $CONTROL_PLANE_IP:$CONTROL_PLANE_PORT"

# Patch kubeconfig server (only in cluster.server line)
sed -i "s#\(server: https://\)[^:]\+:[0-9]\+#\1$CONTROL_PLANE_IP:$CONTROL_PLANE_PORT#g" "$KUBECONFIG"

echo "📄 kubeconfig head (after patch):"
head -n 10 "$KUBECONFIG" || true

# --- Start MCP server in background ---
echo "🚀 Starting MCP server..."
KUBECONFIG="$KUBECONFIG" python k8_mcp_server.py &
MCP_PID=$!
echo "🆔 MCP server PID: $MCP_PID"

# Wait for MCP server to be ready
echo "⏳ Waiting for MCP server health..."
while ! curl -s http://localhost:8001/health >/dev/null 2>&1; do
   echo "   ⏱ Still waiting..."
   sleep 1
done
echo "✅ MCP server ready!"

# --- Start Streamlit (foreground) ---
echo "🚀 Starting Streamlit UI..."
exec streamlit run web_app_kind.py --server.address=0.0.0.0 --server.port=8501 --server.headless=true