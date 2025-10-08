#!/bin/bash
set -euo pipefail

# ==============================
# Cleanup function
# ==============================
cleanup() {
    echo "🛑 Cleaning up background processes..."
    [ -n "${K8_PID:-}" ] && kill "$K8_PID" 2>/dev/null || true
    [ -n "${S3_PID:-}" ] && kill "$S3_PID" 2>/dev/null || true
    [ -n "${STREAMLIT_PID:-}" ] && kill "$STREAMLIT_PID" 2>/dev/null || true
    exit 1
}

# Trap signals and errors
trap cleanup SIGINT SIGTERM ERR

# ==============================
# Health check function
# ==============================
check_health() {
  local name=$1
  local port=$2
  local retries=30

  echo "🔍 Waiting for $name on port $port..."
  for i in $(seq 1 $retries); do
    if curl -fs http://localhost:$port/health >/dev/null; then
      echo "✅ $name ready!"
      return 0
    fi
    sleep 1
  done

  echo "❌ $name failed to become healthy after ${retries}s"
  return 1
}

# ==============================
# Start servers
# ==============================
echo "🚀 Starting Kubernetes MCP server..."
python k8_mcp_server.py > /var/log/k8s_mcp.log 2>&1 &
K8_PID=$!

echo "🚀 Starting AWS S3 MCP server..."
python aws_s3_server.py > /var/log/s3_mcp.log 2>&1 &
S3_PID=$!

# ==============================
# Run health checks in background
# ==============================
check_health "Kubernetes MCP server" 8001 &
K8_HEALTH_PID=$!

check_health "AWS S3 MCP server" 8011 &
S3_HEALTH_PID=$!

# Wait for the first health check success
if wait -n $K8_HEALTH_PID $S3_HEALTH_PID; then
  echo "🎉 At least one MCP server is ready, starting Streamlit..."
else
  echo "❌ Both MCP servers failed health checks!"
  cleanup
fi

# ==============================
# Start Streamlit in foreground
# ==============================
echo "🚀 Starting Streamlit..."
streamlit run web_app.py \
  --server.address=0.0.0.0 \
  --server.port=8501 \
  --server.headless=true &
STREAMLIT_PID=$!

# ==============================
# Monitor all processes
# ==============================
# If *any* child process dies, cleanup
wait -n $K8_PID $S3_PID $STREAMLIT_PID
echo "⚠️ One process exited unexpectedly. Triggering cleanup..."
cleanup
