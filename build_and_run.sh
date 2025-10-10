#!/bin/bash
set -e

echo "🚀 Building and running Kubernetes + AWS S3 Chat Application..."

# --- Check .env file ---
if [ ! -f .env ]; then
    echo "❌ .env file not found! Please create one from .env.example"
    echo "   cp .env.example .env"
    echo "   Then edit .env with your DEEPSEEK_API_KEY"
    exit 1
fi

if ! grep -q "DEEPSEEK_API_KEY=" .env || grep -q "DEEPSEEK_API_KEY=your_mistral_api_key" .env; then
    echo "❌ Please set your DEEPSEEK_API_KEY in the .env file"
    exit 1
fi

# --- Check kubectl config ---
if [ ! -d ~/.kube ] || [ ! -f ~/.kube/config ]; then
    echo "⚠️  Warning: No kubectl configuration found at ~/.kube/config"
    read -p "   Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# --- Check ports ---
for port in 8501 8000 8001 8010 8011; do
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null ; then
        echo "⚠️  Port $port is already in use!"
    fi
done

# --- Create data directory ---
mkdir -p ./data

# --- Build Docker images ---
echo "🏗️  Building Docker images..."
docker compose build

# --- Start services ---
echo "🚀 Starting services..."
docker compose up -d

# --- Wait for services ---
echo "⏳ Waiting for services to be ready..."
MAX_WAIT=12
WAIT_TIME=0
while [ $WAIT_TIME -lt $MAX_WAIT ]; do
    K8S_MCP_HEALTH=$(docker compose exec -T kubernetes-chat curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/health || echo "000")
    S3_MCP_HEALTH=$(docker compose exec -T kubernetes-chat curl -s -o /dev/null -w "%{http_code}" http://localhost:8011/health || echo "000")
    STREAMLIT_HEALTH=$(docker compose exec -T kubernetes-chat curl -s -o /dev/null -w "%{http_code}" http://localhost:8501 || echo "000")

    if [ "$K8S_MCP_HEALTH" = "200" ] && [ "$S3_MCP_HEALTH" = "200" ] && [ "$STREAMLIT_HEALTH" = "200" ]; then
        echo "✅ All services are ready!"
        break
    fi

    sleep 2
    WAIT_TIME=$((WAIT_TIME + 2))
    echo "   Waiting... ${WAIT_TIME}s"
done

if [ $WAIT_TIME -ge $MAX_WAIT ]; then
    echo "❌ Services did not start in time. Check logs:"
    docker compose logs
    exit 1
fi

# --- Final status ---
if docker compose ps | grep -q "Up"; then
    echo "✅ Services are running!"
    echo ""
    echo "🌐 Access your application at:"
    echo "   Streamlit UI: http://localhost:8501"
    echo "   Kubernetes MCP Health: http://localhost:8001/health"
    echo "   AWS S3 MCP Health:    http://localhost:8011/health"
    echo ""
    echo "📋 Useful commands:"
    echo "   View logs:    docker compose logs -f"
    echo "   Stop:         docker compose down"
    echo "   Restart:      docker compose restart"
    echo ""
    echo "🔧 Troubleshooting:"
    echo "   Check logs:   docker compose logs"
    echo "   Shell access: docker compose exec kubernetes-chat bash"
else
    echo "❌ Services failed to start. Check logs:"
    docker compose logs
    exit 1
fi
