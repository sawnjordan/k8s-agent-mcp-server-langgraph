
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

```python

pip install -r requirements.txt
```

4. **Create a .env file in the project root and add your API keys:**

```bash
MISTRAL_API_KEY=your_mistral_key
```

3. **Running the Project:**

##### Open two separate terminals:

- Terminal 1 - Custom MCP Server - Start the MCP server:

```python
python k8_mcp_server.py
```

This will run your Kubernetes MCP server and expose the tools via streamable-http transport.

- Terminal 2 - MCP Client

You can interact with the MCP server in two ways:

+ Option 1: Run the client script


```python
python mcp_client_langgraph.py
```
This runs a CLI-based interaction using LangGraph.

+ Option 2: Run the Streamlit web app

```python
streamlit run web_app_kind.py
```

#### Sample Prompt

```
List pods on <custom-name> namespace
```

## Using Docker for build and run

### If you are using Kind Cluster on local

- Create `.env.kind` file as shown on `.env.kind.sample`.
- Run below commands: 
```
chmod +x ./get_kind_control_plane.sh`
chmod +x ./build_and_run_kind.sh
```
- To get the kind cluster control plane IP and Port run  below command:
```bash
./get_kind_control_plane.sh
```
**Note:** You can copy the output on `.env.kind`.
 - To build and run the MCP servers and web UI.
```bash
./build_and_run_kind.sh
```

## If you are using Cluster on Cloud (AWS)

- Create `.env.aws` file with the AWS credentials as shown on `.env.aws.example`
- Run below command
```bash
chmod +x ./build_and_run.sh
./build_and_run.sh
```

### Chat History

- Chat history are saved on `./data/`.