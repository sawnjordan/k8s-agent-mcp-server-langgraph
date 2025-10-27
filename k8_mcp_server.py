import subprocess
from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
import threading
import time
import os

# --- Initialize MCP server for Kubernetes ---
# Bind to 0.0.0.0 so other containers can reach it
mcp = FastMCP("Kubernetes", host="0.0.0.0", port=8000)

# --- FastAPI app for health ---
k8s_health_app = FastAPI()

@k8s_health_app.get("/health")
def health_check():
    return JSONResponse(content={"status": "ok"})

# --- Detect if running inside a container ---
def running_in_container() -> bool:
    return os.path.exists("/.dockerenv") or os.environ.get("KUBERNETES_CHAT_CONTAINER") == "true"

active_forwards = {}

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

# --- Start port-forward ---
def start_port_forward(target_type: str, name: str, local_port: int, remote_port: int, namespace: str):
    key = f"{target_type}/{namespace}/{name}"

    if key in active_forwards:
        return f"⚠️ Port-forward already active for {key} on local port {active_forwards[key]['local_port']}"

    # Bind address based on environment
    addr = "0.0.0.0" if running_in_container() else "127.0.0.1"

    cmd = [
        "kubectl",
        "port-forward",
        f"{target_type}/{name}",
        f"{local_port}:{remote_port}",
        "-n",
        namespace,
        "--address", addr
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    active_forwards[key] = {
        "proc": proc,
        "local_port": local_port,
        "remote_port": remote_port,
        "namespace": namespace,
        "target_type": target_type
    }

    msg = f"✅ Port-forward active: {target_type}/{name}:{remote_port} -> local port {local_port}"
    if running_in_container():
        msg += f"\n⚠️ You are inside a container. Ensure this port is exposed in docker-compose.yml, e.g. - \"{local_port}:{local_port}\""
        msg += f"\nAccess it on host at http://localhost:{local_port}"
    else:
        msg += f"\nAccess it at http://localhost:{local_port}"
    return msg

# --- Stop port-forward ---
def stop_port_forward(target_type: str, name: str, namespace: str = "default") -> str:
    key = f"{target_type}/{namespace}/{name}"
    if key not in active_forwards:
        return f"No active port-forward found for {key}"

    proc = active_forwards[key]["proc"]
    proc.terminate()
    proc.wait()
    del active_forwards[key]

    return f"Port-forward stopped for {key}"


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

@mcp.tool(name="exec_pod", description="Execute a command inside a pod (non-interactive)")
def exec_pod(pod_name: str, namespace: str = "default", command: str = "ls /") -> str:
    """
    Execute a non-interactive command inside a Kubernetes pod and return the output.
    Suitable for chat or UI environments (no TTY).
    """
    return run_kubectl(
        f"kubectl exec {pod_name} -n {namespace} -- {command}",
        f"Failed to execute command in pod '{pod_name}'."
    )

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

# --- RBAC & Security ---
@mcp.tool(name="whoami", description="Show the current Kubernetes identity")
def whoami() -> str:
    return run_kubectl("kubectl auth whoami", "Unable to determine Kubernetes identity.")

@mcp.tool(name="can_i", description="Check if the current user can perform an action on a resource")
def can_i(verb: str, resource: str, namespace: str = "default") -> str:
    return run_kubectl(f"kubectl auth can-i {verb} {resource} -n {namespace}", "Unable to check permissions.")

@mcp.tool(name="get_roles", description="List all Roles in a namespace")
def get_roles(namespace: str = "default") -> str:
    return run_kubectl(f"kubectl get roles -n {namespace}", f"No Roles found in '{namespace}' namespace.")

@mcp.tool(name="get_cluster_roles", description="List all ClusterRoles")
def get_cluster_roles() -> str:
    return run_kubectl("kubectl get clusterroles", "No ClusterRoles found.")

@mcp.tool(name="get_rolebindings", description="List all RoleBindings in a namespace")
def get_rolebindings(namespace: str = "default") -> str:
    return run_kubectl(f"kubectl get rolebindings -n {namespace}", f"No RoleBindings found in '{namespace}' namespace.")

@mcp.tool(name="get_clusterrolebindings", description="List all ClusterRoleBindings")
def get_clusterrolebindings() -> str:
    return run_kubectl("kubectl get clusterrolebindings", "No ClusterRoleBindings found.")

# --- Workloads: StatefulSets, DaemonSets, Jobs ---
@mcp.tool(name="get_statefulsets", description="List all StatefulSets in a namespace")
def get_statefulsets(namespace: str = "default") -> str:
    return run_kubectl(f"kubectl get statefulsets -n {namespace}", f"No StatefulSets found in '{namespace}' namespace.")

@mcp.tool(name="describe_statefulset", description="Describe a StatefulSet in a namespace")
def describe_statefulset(name: str, namespace: str = "default") -> str:
    return run_kubectl(f"kubectl describe statefulset {name} -n {namespace}", f"StatefulSet '{name}' not found in '{namespace}' namespace.")

@mcp.tool(name="get_daemonsets", description="List all DaemonSets in a namespace")
def get_daemonsets(namespace: str = "default") -> str:
    return run_kubectl(f"kubectl get daemonsets -n {namespace}", f"No DaemonSets found in '{namespace}' namespace.")

@mcp.tool(name="describe_daemonset", description="Describe a DaemonSet in a namespace")
def describe_daemonset(name: str, namespace: str = "default") -> str:
    return run_kubectl(f"kubectl describe daemonset {name} -n {namespace}", f"DaemonSet '{name}' not found in '{namespace}' namespace.")

@mcp.tool(name="get_jobs", description="List all Jobs in a namespace")
def get_jobs(namespace: str = "default") -> str:
    return run_kubectl(f"kubectl get jobs -n {namespace}", f"No Jobs found in '{namespace}' namespace.")

@mcp.tool(name="describe_job", description="Describe a Job in a namespace")
def describe_job(name: str, namespace: str = "default") -> str:
    return run_kubectl(f"kubectl describe job {name} -n {namespace}", f"Job '{name}' not found in '{namespace}' namespace.")

@mcp.tool(name="get_cronjobs", description="List all CronJobs in a namespace")
def get_cronjobs(namespace: str = "default") -> str:
    return run_kubectl(f"kubectl get cronjobs -n {namespace}", f"No CronJobs found in '{namespace}' namespace.")

@mcp.tool(name="describe_cronjob", description="Describe a CronJob in a namespace")
def describe_cronjob(name: str, namespace: str = "default") -> str:
    return run_kubectl(f"kubectl describe cronjob {name} -n {namespace}", f"CronJob '{name}' not found in '{namespace}' namespace.")


# --- Storage: PV, PVC, StorageClasses ---
@mcp.tool(name="get_pvs", description="List all PersistentVolumes (PVs)")
def get_pvs() -> str:
    return run_kubectl("kubectl get pv", "No PersistentVolumes found in the cluster.")

@mcp.tool(name="describe_pv", description="Describe a PersistentVolume")
def describe_pv(name: str) -> str:
    return run_kubectl(f"kubectl describe pv {name}", f"PersistentVolume '{name}' not found.")

@mcp.tool(name="get_pvcs", description="List all PersistentVolumeClaims (PVCs) in a namespace")
def get_pvcs(namespace: str = "default") -> str:
    return run_kubectl(f"kubectl get pvc -n {namespace}", f"No PVCs found in '{namespace}' namespace.")

@mcp.tool(name="describe_pvc", description="Describe a PersistentVolumeClaim in a namespace")
def describe_pvc(name: str, namespace: str = "default") -> str:
    return run_kubectl(f"kubectl describe pvc {name} -n {namespace}", f"PVC '{name}' not found in '{namespace}' namespace.")

@mcp.tool(name="get_storageclasses", description="List all StorageClasses")
def get_storageclasses() -> str:
    return run_kubectl("kubectl get sc", "No StorageClasses found in the cluster.")


# --- Pod Debugging ---
@mcp.tool(name="get_pending_pods", description="List pods stuck in Pending state (optionally for a specific namespace)")
def get_pending_pods(namespace: str = None) -> str:
    ns_flag = f"-n {namespace}" if namespace else "--all-namespaces"
    return run_kubectl(
        f"kubectl get pods {ns_flag} --field-selector=status.phase=Pending",
        "No pending pods found."
    )

@mcp.tool(name="get_crashloop_pods", description="List pods in CrashLoopBackOff (optionally for a specific namespace)")
def get_crashloop_pods(namespace: str = None) -> str:
    ns_flag = f"-n {namespace}" if namespace else "--all-namespaces"
    return run_kubectl(
        f"kubectl get pods {ns_flag} | grep CrashLoopBackOff",
        "No CrashLoopBackOff pods found."
    )

@mcp.tool(name="logs_all_containers", description="Get logs from all containers in a pod")
def logs_all_containers(pod_name: str, namespace: str = "default") -> str:
    return run_kubectl(
        f"kubectl logs {pod_name} -n {namespace} --all-containers=true",
        f"No logs found for pod '{pod_name}' in '{namespace}' namespace."
    )


# --- Rollout / Deployment Debugging ---
@mcp.tool(name="rollout_status", description="Check rollout status of a deployment")
def rollout_status(deployment_name: str, namespace: str = "default") -> str:
    return run_kubectl(
        f"kubectl rollout status deployment {deployment_name} -n {namespace}",
        f"Deployment '{deployment_name}' not found in '{namespace}' namespace."
    )

@mcp.tool(name="rollout_restart", description="Restart a deployment by forcing a new rollout")
def rollout_restart(deployment_name: str, namespace: str = "default") -> str:
    return run_kubectl(
        f"kubectl rollout restart deployment {deployment_name} -n {namespace}",
        f"Failed to restart deployment '{deployment_name}' in '{namespace}' namespace."
    )

@mcp.tool(name="rollback_deployment", description="Rollback a deployment to its previous version")
def rollback_deployment(deployment_name: str, namespace: str = "default") -> str:
    return run_kubectl(
        f"kubectl rollout undo deployment {deployment_name} -n {namespace}",
        f"Failed to rollback deployment '{deployment_name}' in '{namespace}' namespace."
    )

@mcp.tool(name="rollout_history", description="Show rollout history of a deployment")
def rollout_history(deployment_name: str, namespace: str = "default") -> str:
    return run_kubectl(
        f"kubectl rollout history deployment {deployment_name} -n {namespace}",
        f"No rollout history found for deployment '{deployment_name}' in '{namespace}' namespace."
    )

# --- Networking & Connectivity ---
@mcp.tool(name="get_endpoints", description="List all endpoints in a namespace")
def get_endpoints(namespace: str = "default") -> str:
    return run_kubectl(
        f"kubectl get endpoints -n {namespace}",
        f"No endpoints found in '{namespace}' namespace."
    )

@mcp.tool(name="port_forward_service", description="Forward a local port to a service port")
def port_forward_service(service_name: str, local_port: int = None, remote_port: int = None, namespace: str = "default") -> str:
    # Auto-detect service port
    if remote_port is None:
        try:
            svc_output = run_kubectl(f"kubectl get service {service_name} -n {namespace} -o json")
            svc_data = json.loads(svc_output)
            remote_port = svc_data["spec"]["ports"][0]["port"]
        except Exception as e:
            return f"Failed to detect service port for '{service_name}': {str(e)}"

    if local_port is None:
        local_port = remote_port

    return start_port_forward("service", service_name, local_port, remote_port, namespace)

@mcp.tool(name="port_forward_pod", description="Forward a local port to a pod port")
def port_forward_pod(pod_name: str, local_port: int = None, remote_port: int = None, namespace: str = "default") -> str:
    # Auto-detect pod container port
    if remote_port is None:
        try:
            pod_output = run_kubectl(f"kubectl get pod {pod_name} -n {namespace} -o json")
            pod_data = json.loads(pod_output)
            containers = pod_data["spec"]["containers"]
            if "ports" in containers[0] and containers[0]["ports"]:
                remote_port = containers[0]["ports"][0]["containerPort"]
            else:
                return f"No container ports found in pod '{pod_name}', please specify remote_port manually."
        except Exception as e:
            return f"Failed to detect pod container port for '{pod_name}': {str(e)}"

    if local_port is None:
        local_port = remote_port

    return start_port_forward("pod", pod_name, local_port, remote_port, namespace)

@mcp.tool(name="stop_port_forward", description="Stop an active port-forward")
def stop_port_forward_tool(name: str, namespace: str = "default", target_type: str = "service") -> str:
    return stop_port_forward(target_type, name, namespace)

@mcp.tool(name="test_dns", description="Test DNS resolution inside the cluster using busybox")
def test_dns() -> str:
    return run_kubectl(
        "kubectl run dns-test --rm --image=busybox --restart=Never -- nslookup kubernetes.default",
        "Failed to resolve DNS inside the cluster."
    )


# --- Node Debugging ---
@mcp.tool(name="describe_node", description="Describe a node in the cluster")
def describe_node(node_name: str) -> str:
    return run_kubectl(
        f"kubectl describe node {node_name}",
        f"Node '{node_name}' not found."
    )

@mcp.tool(name="cordon_node", description="Mark a node as unschedulable")
def cordon_node(node_name: str) -> str:
    return run_kubectl(
        f"kubectl cordon {node_name}",
        f"Failed to cordon node '{node_name}'."
    )

@mcp.tool(name="uncordon_node", description="Mark a node as schedulable")
def uncordon_node(node_name: str) -> str:
    return run_kubectl(
        f"kubectl uncordon {node_name}",
        f"Failed to uncordon node '{node_name}'."
    )

@mcp.tool(name="drain_node", description="Drain a node by evicting workloads (ignoring daemonsets)")
def drain_node(node_name: str) -> str:
    return run_kubectl(
        f"kubectl drain {node_name} --ignore-daemonsets --delete-emptydir-data",
        f"Failed to drain node '{node_name}'."
    )


# --- YAML / Config Inspection ---
@mcp.tool(name="get_resource_yaml", description="Get full YAML definition of a resource")
def get_resource_yaml(kind: str, name: str, namespace: str = "default") -> str:
    ns_part = f"-n {namespace}" if namespace else ""
    return run_kubectl(
        f"kubectl get {kind} {name} {ns_part} -o yaml",
        f"Resource {kind}/{name} not found in namespace '{namespace}'."
    )

@mcp.tool(name="diff_manifest", description="Run kubectl diff on a manifest before applying")
def diff_manifest(file_path: str) -> str:
    return run_kubectl(
        f"kubectl diff -f {file_path}",
        f"No differences found for manifest {file_path}."
    )

# --- Kubernetes Context Management ---
@mcp.tool(name="get_current_context", description="Get the current Kubernetes context")
def get_current_context() -> str:
    return run_kubectl(
        "kubectl config current-context",
        "Unable to get the current Kubernetes context."
    )

@mcp.tool(name="switch_context", description="Switch to a different Kubernetes context")
def switch_context(context_name: str) -> str:
    return run_kubectl(
        f"kubectl config use-context {context_name}",
        f"Failed to switch to context '{context_name}'. Make sure it exists."
    )

@mcp.tool(name="list_contexts", description="List all Kubernetes contexts in your kubeconfig")
def list_contexts() -> str:
    return run_kubectl(
        "kubectl config get-contexts -o name",
        "No contexts found in your kubeconfig."
    )

# --- Run MCP server ---
def run_k8s_mcp():
    print("Kubernetes MCP server running on port 8000")
    mcp.run(transport="streamable-http")

# --- Run Health server ---
def run_k8s_health_server():
    print("Kubernetes Health server running on port 8001")
    uvicorn.run(k8s_health_app, host="0.0.0.0", port=8001)

if __name__ == "__main__":
    # Start both servers in separate threads
    threading.Thread(target=run_k8s_mcp, daemon=True).start()
    threading.Thread(target=run_k8s_health_server, daemon=True).start()

    # Keep main thread alive
    while True:
        time.sleep(1)
