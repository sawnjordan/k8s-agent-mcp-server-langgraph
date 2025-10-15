
# Kubernetes & S3 MCP Servers with LangGraph + Streamlit
This project implements a multi-server MCP (Multi-Server Chat Protocol) setup integrating:

🧩 LangGraph for multi-agent orchestration

🤖 DeepSeek or MistralAI as the LLM backend

☸️ Kubernetes MCP Server for managing and querying clusters

🪣 S3 MCP Server for S3-based data management

💬 Streamlit UI for interactive conversation with both servers

## Prerequisites
Before you start, ensure the following requirements are met.

### System Requirements

- Platform: Linux (recommended) or macOS

- Python ≥ 3.10

- Docker and Docker Compose v2+ installed

- kubectl CLI configured and working

- Git installed

### For Kubernetes MCP Server

Depending on your environment:

### 🧱 Local (Kind) Cluster

- You must have Kind installed and a cluster created:

```
kind get clusters
```

- Verify connectivity:
```
kubectl get nodes
```

- Your local kubeconfig (~/.kube/config) must be accessible.

### ☁️ Cloud Cluster (EKS / GKE / AKS)

- Configure your cluster credentials locally( Any cloud ). Below one is for AWS.
```
aws eks update-kubeconfig --name <cluster-name> --region <region> --profile <aws-profile>
```

- Confirm access:
```
kubectl get pods -A
```

- 🧩 The MCP Server reads your kubeconfig inside the container.

### 🪣 For S3 MCP Server

To enable the S3 integration:

- Create a .env.aws file (based on .env.aws.example):

```
AWS_ACCESS_KEY_ID=<your-access-key>
AWS_SECRET_ACCESS_KEY=<your-secret-key>
AWS_DEFAULT_REGION=<your-region>
```

These credentials must have s3:* and (optionally) kms:* permissions.

- This file is required for S3 MCP to authenticate successfully.

- If using AWS SSO instead of static keys, make sure your host machine has valid SSO config under ~/.aws/config

You can verify it with:
```
aws sts get-caller-identity --profile <profile-name>
```

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
OR
DEEPSEEK_API_KEY=your_mistral_key
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
streamlit run web_app.py
```

#### Sample Prompt

```
List pods on <custom-name> namespace
```

## Using Docker for build and run

### If you are using Kind Cluster on local

**Note**: If you are using other local cluster then kind no need to do below:

- Create `.env.kind` file as shown on `.env.kind.sample`.
- Run below commands: 
```
chmod +x ./get_kind_control_plane.sh
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

- Create `.env.aws` file with the AWS credentials as shown on `.env.aws.example`. **This is required for s3 mcp server.**
- Run below command
```bash
chmod +x ./build_and_run.sh
./build_and_run.sh
```

### Chat History

- Chat history are saved on `./data/`.