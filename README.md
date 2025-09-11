
# Kubernetes MCP Server-Client with LangGraph and Streamlit
This project provides a Kubernetes-focused MCP (Multi-Server Chat Protocol) setup using LangGraph, MistralAI, and Streamlit for interactive queries and management.

## Environment Setup

1. **Clone the repository**:

```bash
git clone https://github.com/sanjog-lama/k8s-agent-mcp-server-langgraph.git
cd k8s-agent-mcp-server-langgraph
```

2. **Create and activate a virtual environment:**

```bash

python3 -m venv venv
source venv/bin/activate
```

3. **Install required packages:**

```bash

pip install -r requirements.txt
```

4. **Create a .env file in the project root and add your API keys:**

```
MISTRAL_API_KEY=your_mistral_key
```

3. **Running the Project:**

##### Open two separate terminals:

- Terminal 1 - Custom MCP Server - Start the MCP server:

```
python k8_mcp_server.py
```

This will run your Kubernetes MCP server and expose the tools via streamable-http transport.

- Terminal 2 - MCP Client

You can interact with the MCP server in two ways:

+ Option 1: Run the client script


```
python mcp_client_langgraph.py
```
This runs a CLI-based interaction using LangGraph.

+ Option 2: Run the Streamlit web app

```
streamlit run web_app.py
```

#### Sample Prompt

```
List pods on <custom-name> namespace
```