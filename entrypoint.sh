#!/bin/bash
set -e

# Start MCP server in background
python k8_mcp_server.py &
MCP_PID=$!

# Wait for MCP server to be ready
echo "Waiting for MCP server..."
while ! curl -s http://localhost:8001/health >/dev/null 2>&1; do
    sleep 1
done
echo "✅ MCP server ready!"

# Start Streamlit (runs in foreground)
exec streamlit run web_app.py --server.address=0.0.0.0 --server.port=8501 --server.headless=true
