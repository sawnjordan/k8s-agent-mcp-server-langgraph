import subprocess
from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("Kubernetes")

# --- Utility: run kubectl safely ---
def run_kubectl(command: str, empty_msg: str = None) -> str:
    """Run a kubectl command and return output, friendly message if empty, or unknown command."""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, check=True
        )
        output = result.stdout.strip()
        if not output:
            return empty_msg or "No resources found for your query."
        return output
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.strip()
        if "unknown command" in stderr or "no resources found" in stderr.lower():
            return "Sorry, I don’t have a tool for that action yet."
        return f"Error: {stderr}"



# --- Core resources ---
@mcp.tool(name="get_nodes", description="List all nodes in the cluster")
def get_nodes() -> str:
    return run_kubectl("kubectl get nodes", "No nodes found in the cluster.")

@mcp.tool(name="get_namespaces", description="List all namespaces in the cluster")
def get_namespaces() -> str:
    return run_kubectl("kubectl get namespaces", "No namespaces found in the cluster.")

@mcp.tool(name="get_pods", description="List all pods in a namespace (default is 'default')")
def get_pods(namespace: str = "default") -> str:
    return run_kubectl(f"kubectl get pods -n {namespace}", f"No pods found in '{namespace}' namespace.")

@mcp.tool(name="describe_pod", description="Describe a pod in a namespace")
def describe_pod(pod_name: str, namespace: str = "default") -> str:
    return run_kubectl(f"kubectl describe pod {pod_name} -n {namespace}", f"Pod '{pod_name}' not found in '{namespace}' namespace.")

@mcp.tool(name="get_pod_logs", description="Get logs from a pod, optionally specify container")
def get_pod_logs(pod_name: str, namespace: str = "default", container: str = "") -> str:
    container_part = f"-c {container}" if container else ""
    return run_kubectl(f"kubectl logs {pod_name} -n {namespace} {container_part}", f"No logs found for pod '{pod_name}' in '{namespace}' namespace.")

@mcp.tool(name="exec_pod", description="Execute a command inside a pod")
def exec_pod(pod_name: str, namespace: str = "default", command: str = "/bin/sh") -> str:
    return run_kubectl(f"kubectl exec -it {pod_name} -n {namespace} -- {command}", f"Failed to execute command in pod '{pod_name}'.")


# --- Deployments ---
@mcp.tool(name="get_deployments", description="List all deployments in a namespace")
def get_deployments(namespace: str = "default") -> str:
    return run_kubectl(f"kubectl get deployments -n {namespace}", f"No deployments found in '{namespace}' namespace.")

@mcp.tool(name="describe_deployment", description="Describe a deployment in a namespace")
def describe_deployment(deployment_name: str, namespace: str = "default") -> str:
    return run_kubectl(f"kubectl describe deployment {deployment_name} -n {namespace}", f"Deployment '{deployment_name}' not found in '{namespace}' namespace.")

@mcp.tool(name="scale_deployment", description="Scale a deployment to a specific number of replicas")
def scale_deployment(deployment_name: str, replicas: int, namespace: str = "default") -> str:
    return run_kubectl(f"kubectl scale deployment {deployment_name} --replicas={replicas} -n {namespace}", f"Failed to scale deployment '{deployment_name}'.")


# --- Services ---
@mcp.tool(name="get_services", description="List all services in a namespace")
def get_services(namespace: str = "default") -> str:
    return run_kubectl(f"kubectl get services -n {namespace}", f"No services found in '{namespace}' namespace.")

@mcp.tool(name="describe_service", description="Describe a service in a namespace")
def describe_service(service_name: str, namespace: str = "default") -> str:
    return run_kubectl(f"kubectl describe service {service_name} -n {namespace}", f"Service '{service_name}' not found in '{namespace}' namespace.")


# --- Ingress ---
@mcp.tool(name="get_ingresses", description="List all ingresses in a namespace")
def get_ingresses(namespace: str = "default") -> str:
    return run_kubectl(f"kubectl get ingresses -n {namespace}", f"No ingresses found in '{namespace}' namespace.")

@mcp.tool(name="describe_ingress", description="Describe an ingress in a namespace")
def describe_ingress(ingress_name: str, namespace: str = "default") -> str:
    return run_kubectl(f"kubectl describe ingress {ingress_name} -n {namespace}", f"Ingress '{ingress_name}' not found in '{namespace}' namespace.")


# --- ConfigMaps & Secrets ---
@mcp.tool(name="get_configmaps", description="List all ConfigMaps in a namespace")
def get_configmaps(namespace: str = "default") -> str:
    return run_kubectl(f"kubectl get configmaps -n {namespace}", f"No ConfigMaps found in '{namespace}' namespace.")

@mcp.tool(name="describe_configmap", description="Describe a ConfigMap in a namespace")
def describe_configmap(configmap_name: str, namespace: str = "default") -> str:
    return run_kubectl(f"kubectl describe configmap {configmap_name} -n {namespace}", f"ConfigMap '{configmap_name}' not found in '{namespace}' namespace.")

@mcp.tool(name="get_secrets", description="List all Secrets in a namespace")
def get_secrets(namespace: str = "default") -> str:
    return run_kubectl(f"kubectl get secrets -n {namespace}", f"No Secrets found in '{namespace}' namespace.")

@mcp.tool(name="describe_secret", description="Describe a Secret in a namespace")
def describe_secret(secret_name: str, namespace: str = "default") -> str:
    return run_kubectl(f"kubectl describe secret {secret_name} -n {namespace}", f"Secret '{secret_name}' not found in '{namespace}' namespace.")


# --- Events & Metrics ---
@mcp.tool(name="get_events", description="List events in a namespace")
def get_events(namespace: str = "default") -> str:
    return run_kubectl(f"kubectl get events -n {namespace}", f"No events found in '{namespace}' namespace.")

@mcp.tool(name="top_pods", description="Show pod metrics in a namespace")
def top_pods(namespace: str = "default") -> str:
    return run_kubectl(f"kubectl top pods -n {namespace}", f"No pod metrics found in '{namespace}' namespace.")

@mcp.tool(name="top_nodes", description="Show metrics for all nodes")
def top_nodes() -> str:
    return run_kubectl("kubectl top nodes", "No node metrics found.")

@mcp.tool(name="get_unhealthy_pods", description="List all pods in all namespaces that are unhealthy")
def get_unhealthy_pods_all_namespaces() -> str:
    return run_kubectl(
        "kubectl get pods --all-namespaces --no-headers | grep -E 'CrashLoopBackOff|OOMKilled|ImagePullBackOff|ErrImagePull'",
        "No unhealthy pods found across all namespaces."
    )


# --- Run MCP server ---
if __name__ == "__main__":
    mcp.run(transport="streamable-http")
