import boto3
from botocore.exceptions import ClientError
from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
import threading
import json

# --- Initialize MCP server for AWS S3 ---
s3_mcp = FastMCP("AWS S3", port=8010)

# --- FastAPI app for health ---
s3_health_app = FastAPI()

@s3_health_app.get("/health")
def health_check():
    try:
        s3 = boto3.client("s3")
        s3.list_buckets()
        return JSONResponse(content={"status": "ok"})
    except ClientError as e:
        return JSONResponse(content={"status": "error", "detail": str(e)}, status_code=500)

# --- Utility function: paginated delete objects ---
def delete_all_objects(s3, bucket_name):
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket_name):
        objects = page.get("Contents", [])
        if objects:
            delete_keys = [{"Key": obj["Key"]} for obj in objects]
            s3.delete_objects(Bucket=bucket_name, Delete={"Objects": delete_keys})

# --- S3 Bucket Operations ---

@s3_mcp.tool(
    name="create_bucket_advanced",
    description="Create an S3 bucket with optional versioning in a specified region"
)
def create_bucket_advanced(bucket_name: str, region: str = "us-east-1", enable_versioning: bool = False) -> str:
    try:
        s3 = boto3.client("s3", region_name=region)
        if region == "us-east-1":
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": region}
            )
        if enable_versioning:
            s3.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={"Status": "Enabled"}
            )
        versioning_status = "with versioning enabled" if enable_versioning else "without versioning"
        return f"Bucket '{bucket_name}' created successfully in region '{region}' {versioning_status}."
    except ClientError as e:
        return f"Error: {e}"

@s3_mcp.tool(
    name="delete_bucket_interactive",
    description="Delete an S3 bucket. If not empty, ask for confirmation before deleting all objects."
)
def delete_bucket_interactive(bucket_name: str, confirm: str = "no") -> str:
    s3 = boto3.client("s3")
    try:
        # Check if bucket has objects
        response = s3.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
        objects_exist = response.get("KeyCount", 0) > 0

        if objects_exist and confirm.lower() != "yes":
            return (
                f"Bucket '{bucket_name}' is not empty. Are you sure you want to delete it? "
                "Pass confirm='yes' to delete all objects and the bucket."
            )

        # Delete all objects if bucket not empty
        if objects_exist:
            delete_all_objects(s3, bucket_name)

        # Delete the bucket
        s3.delete_bucket(Bucket=bucket_name)
        return f"Bucket '{bucket_name}' and all its objects have been deleted."
    except ClientError as e:
        return f"Error: {e}"

@s3_mcp.tool(name="list_buckets", description="List all S3 buckets")
def list_buckets() -> str:
    try:
        s3 = boto3.client("s3")
        response = s3.list_buckets()
        buckets = [b["Name"] for b in response.get("Buckets", [])]
        return "\n".join(buckets) if buckets else "No buckets found."
    except ClientError as e:
        return f"Error: {e}"

@s3_mcp.tool(name="get_bucket_location", description="Get the AWS region of a bucket")
def get_bucket_location(bucket_name: str) -> str:
    try:
        s3 = boto3.client("s3")
        loc = s3.get_bucket_location(Bucket=bucket_name)
        region = loc.get("LocationConstraint") or "us-east-1"
        return f"Bucket '{bucket_name}' is in region '{region}'."
    except ClientError as e:
        return f"Error: {e}"

@s3_mcp.tool(name="set_bucket_versioning", description="Enable or suspend versioning for a bucket")
def set_bucket_versioning(bucket_name: str, status: str) -> str:
    try:
        s3 = boto3.client("s3")
        s3.put_bucket_versioning(Bucket=bucket_name, VersioningConfiguration={"Status": status})
        return f"Bucket '{bucket_name}' versioning set to '{status}'."
    except ClientError as e:
        return f"Error: {e}"

# --- S3 Object Operations ---

@s3_mcp.tool(name="list_objects", description="List objects in a bucket with optional prefix")
def list_objects(bucket_name: str, prefix: str = "") -> str:
    try:
        s3 = boto3.client("s3")
        paginator = s3.get_paginator('list_objects_v2')
        all_objects = []
        for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
            all_objects.extend([obj["Key"] for obj in page.get("Contents", [])])
        if not all_objects:
            return f"No objects found in bucket '{bucket_name}' with prefix '{prefix}'."
        return "\n".join(all_objects)
    except ClientError as e:
        return f"Error: {e}"

@s3_mcp.tool(name="upload_file", description="Upload a file to a bucket")
def upload_file(bucket_name: str, file_path: str, s3_key: str) -> str:
    try:
        s3 = boto3.client("s3")
        s3.upload_file(file_path, bucket_name, s3_key)
        return f"File '{file_path}' uploaded to '{bucket_name}/{s3_key}'."
    except ClientError as e:
        return f"Error: {e}"

@s3_mcp.tool(name="download_file", description="Download a file from a bucket")
def download_file(bucket_name: str, s3_key: str, local_path: str) -> str:
    try:
        s3 = boto3.client("s3")
        s3.download_file(bucket_name, s3_key, local_path)
        return f"File '{bucket_name}/{s3_key}' downloaded to '{local_path}'."
    except ClientError as e:
        return f"Error: {e}"

@s3_mcp.tool(name="delete_object", description="Delete an object from a bucket")
def delete_object(bucket_name: str, s3_key: str) -> str:
    try:
        s3 = boto3.client("s3")
        s3.delete_object(Bucket=bucket_name, Key=s3_key)
        return f"Deleted object '{s3_key}' from bucket '{bucket_name}'."
    except ClientError as e:
        return f"Error: {e}"

# --- Bucket Policy Tools ---

@s3_mcp.tool(name="get_bucket_policy_json", description="Get the JSON policy of a bucket")
def get_bucket_policy_json(bucket_name: str) -> str:
    s3 = boto3.client("s3")
    try:
        policy = s3.get_bucket_policy(Bucket=bucket_name)
        return policy.get("Policy", "Bucket has no policy attached.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchBucketPolicy':
            return f"No policy found for bucket '{bucket_name}'."
        return f"AWS error: {e}"

@s3_mcp.tool(name="set_bucket_policy_json", description="Set a bucket policy from JSON")
def set_bucket_policy_json(bucket_name: str, policy_json: str) -> str:
    s3 = boto3.client("s3")
    try:
        policy_dict = json.loads(policy_json)
        s3.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy_dict))
        return f"Policy applied successfully to bucket '{bucket_name}'."
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e}"
    except ClientError as e:
        return f"AWS error: {e}"

@s3_mcp.tool(name="delete_bucket_policy", description="Delete a bucket policy")
def delete_bucket_policy(bucket_name: str) -> str:
    s3 = boto3.client("s3")
    try:
        s3.delete_bucket_policy(Bucket=bucket_name)
        return f"Policy deleted for bucket '{bucket_name}'."
    except ClientError as e:
        return f"AWS error: {e}"

# --- Update bucket policy (merge JSON) ---
@s3_mcp.tool(
    name="update_bucket_policy_json",
    description="Update an existing bucket policy by merging with new JSON statements."
)
def update_bucket_policy_json(bucket_name: str, new_policy_json: str) -> str:
    s3 = boto3.client("s3")
    try:
        # Get current policy
        try:
            current_policy = s3.get_bucket_policy(Bucket=bucket_name)
            current_policy_dict = json.loads(current_policy.get("Policy", "{}"))
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchBucketPolicy':
                current_policy_dict = {"Version": "2012-10-17", "Statement": []}
            else:
                return f"AWS error: {e}"

        # Merge statements
        new_policy_dict = json.loads(new_policy_json)
        if "Statement" not in new_policy_dict:
            return "New policy JSON must contain a 'Statement' key."
        current_policy_dict.setdefault("Statement", [])
        current_policy_dict["Statement"].extend(new_policy_dict["Statement"])

        # Apply merged policy
        s3.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(current_policy_dict))
        return f"Policy updated successfully for bucket '{bucket_name}'."
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e}"
    except ClientError as e:
        return f"AWS error: {e}"

# --- Run S3 MCP and Health server ---
def run_s3_health_server():
    uvicorn.run(s3_health_app, host="0.0.0.0", port=8011)

if __name__ == "__main__":
    threading.Thread(target=run_s3_health_server, daemon=True).start()
    print("AWS S3 Health server running on port 8011")
    s3_mcp.run(transport="streamable-http")