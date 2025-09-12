#!/bin/bash
set -ex  # <- exit on error and print every command

echo "👤 Running as user: $(whoami)"
echo "📂 Listing /root before anything:"
ls -la /root || true

# --- Fix kubeconfig inside container ---
KUBE_DIR_WRITABLE="/root/.kube-writable"
echo "📂 Creating writable kube directory at $KUBE_DIR_WRITABLE"
mkdir -p "$KUBE_DIR_WRITABLE"

echo "📂 Listing $KUBE_DIR_WRITABLE after mkdir:"
ls -la "$KUBE_DIR_WRITABLE" || true

echo "📄 Copying kubeconfig..."
cp /root/.kube/config "$KUBE_DIR_WRITABLE/config"

echo "📄 Listing $KUBE_DIR_WRITABLE after copy:"
ls -la "$KUBE_DIR_WRITABLE" || true

# Get the Kind control-plane IP
echo "🔧 Updating kubeconfig server address..."
sed -i "s|127.0.0.1:38067|multi-node-control-plane:6443|g" "$KUBE_DIR_WRITABLE/config"

# Export KUBECONFIG so all kubectl calls inside container use it
export KUBECONFIG="$KUBE_DIR_WRITABLE/config"
echo "✅ Using kubeconfig at $KUBECONFIG"
echo "📄 kubeconfig head:"
head -n 10 "$KUBECONFIG"

# --- Start MCP server in background ---
echo "🚀 Starting MCP server..."
KUBECONFIG="$KUBE_DIR_WRITABLE/config" python k8_mcp_server.py &
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
export KUBECONFIG="$KUBE_DIR_WRITABLE/config"
exec streamlit run web_app.py --server.address=0.0.0.0 --server.port=8501 --server.headless=true
