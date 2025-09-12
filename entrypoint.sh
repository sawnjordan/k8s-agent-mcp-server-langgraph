#!/bin/bash
set -e

# Start Kubernetes MCP server in background
python k8_mcp_server.py &
K8S_MCP_PID=$!

# Wait for Kubernetes MCP server health
echo "Waiting for Kubernetes MCP server..."
while ! curl -s http://localhost:8001/health >/dev/null 2>&1; do
    sleep 1
done
echo "✅ Kubernetes MCP server ready!"

# Start S3 MCP server in background
python aws_s3_server.py &
S3_MCP_PID=$!

# Wait for S3 MCP server health
echo "Waiting for AWS S3 MCP server..."
while ! curl -s http://localhost:8011/health >/dev/null 2>&1; do
    sleep 1
done
echo "✅ AWS S3 MCP server ready!"

# Start Streamlit (runs in foreground)
exec streamlit run web_app.py --server.address=0.0.0.0 --server.port=8501 --server.headless=true
