    #!/bin/bash

    # Kubernetes Chat Docker Build and Run Script

    echo "🚀 Building and running Kubernetes Chat Application..."

    # Check if .env file exists
    if [ ! -f .env ]; then
        echo "❌ .env file not found! Please create one from .env.example"
        echo "   cp .env.example .env"
        echo "   Then edit .env with your DEEPSEEK_API_KEY"
        exit 1
    fi

    # Check if MISTRAL_API_KEY is set
    if ! grep -q "DEEPSEEK_API_KEY=" .env || grep -q "DEEPSEEK_API_KEY=your_mistral_api_key" .env; then
        echo "❌ Please set your DEEPSEEK_API_KEY in the .env file"
        exit 1
    fi

    # Check if kubectl config exists
    if [ ! -d ~/.kube ] || [ ! -f ~/.kube/config ]; then
        echo "⚠️  Warning: No kubectl configuration found at ~/.kube/config"
        echo "   Make sure you have kubectl configured to access your Kubernetes cluster"
        read -p "   Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    # Check if ports are available
    for port in 8501 8000; do
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null ; then
            echo "⚠️  Port $port is already in use!"
        fi
    done

    # Create data directory for chat history
    mkdir -p ./data

    echo "🏗️  Building Docker image..."
# docker compose -f docker-compose.kind.yaml build
    docker compose -f docker-compose.kind.yaml build


echo "🚀 Starting services..."
docker compose -f docker-compose.kind.yaml up -d

# Wait for Streamlit to be available
# Wait for both MCP server and Streamlit to be ready
echo "⏳ Waiting for services to be ready..."
MAX_WAIT=12
WAIT_TIME=0
while [ $WAIT_TIME -lt $MAX_WAIT ]; do
    MCP_HEALTH=$(docker compose -f docker-compose.kind.yaml exec -T kubernetes-chat curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/health || echo "000")
    STREAMLIT_HEALTH=$(docker compose -f docker-compose.kind.yaml exec -T kubernetes-chat curl -s -o /dev/null -w "%{http_code}" http://localhost:8501 || echo "000")

    if [ "$MCP_HEALTH" = "200" ] && [ "$STREAMLIT_HEALTH" = "200" ]; then
        echo "✅ Services are ready!"
        break
    fi

    sleep 2
    WAIT_TIME=$((WAIT_TIME + 2))
    echo "   Waiting... ${WAIT_TIME}s"
done

if [ $WAIT_TIME -ge $MAX_WAIT ]; then
    echo "❌ Services did not start in time. Check logs:"
    docker compose -f docker-compose.kind.yaml logs
    exit 1
fi

# Check if services are running
if docker compose -f docker-compose.kind.yaml ps | grep -q "Up"; then
    echo "✅ Services are running!"
    echo ""
    echo "🌐 Access your application at:"
    echo "   Streamlit UI: http://127.0.0.1:8501"
    echo "   MCP Server:   http://127.0.0.1:8000"
    echo ""
    echo "📋 Useful commands:"
    echo "   View logs:    docker compose -f docker-compose.kind.yaml logs -f"
    echo "   Stop:         docker compose -f docker-compose.kind.yaml down"
    echo "   Restart:      docker compose -f docker-compose.kind.yaml restart"
    echo ""
    echo "🔧 Troubleshooting:"
    echo "   Check logs:   docker compose -f docker-compose.kind.yaml logs"
    echo "   Shell access: docker compose -f docker-compose.kind.yaml exec kubernetes-chat bash"
else
    echo "❌ Services failed to start. Check logs:"
    docker compose -f docker-compose.kind.yaml logs
    exit 1
fi