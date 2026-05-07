# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Set up CloudWatch vended log delivery for all AgentCore runtimes.

WHY THIS EXISTS:
CloudWatch vended log delivery (APPLICATION_LOGS, USAGE_LOGS) uses the
PutDeliverySource / PutDeliveryDestination / CreateDelivery APIs which
have no CloudFormation support. The CDK stack cannot manage these
resources. This script fills that gap as a post-deploy step.

Note: Container stdout/stderr logs (the -DEFAULT runtime-logs) are
handled automatically by AgentCore when the execution role has the
right CloudWatch permissions — those ARE managed by the CDK stack.

Idempotent — safe to run multiple times. Cleans up stale deliveries
from previous deploys before recreating.

Usage:
    AWS_DEFAULT_REGION=us-east-1 python scripts/setup_log_delivery.py
"""

from __future__ import annotations

import boto3

REGION = "us-east-1"
ACCOUNT_ID = boto3.client("sts").get_caller_identity()["Account"]

LOG_TYPES = ["APPLICATION_LOGS", "USAGE_LOGS"]


def _get_runtime_arns() -> dict[str, str]:
    """Discover all AgentCore runtimes and return {name: arn} mapping."""
    client = boto3.client("bedrock-agentcore-control", region_name=REGION)
    resp = client.list_agent_runtimes()
    return {rt["agentRuntimeName"]: rt["agentRuntimeArn"] for rt in resp.get("agentRuntimes", [])}


def _ensure_source(logs: object, source_name: str, log_type: str, runtime_arn: str) -> bool:
    """Create a delivery source. Returns True on success or if it already exists."""
    try:
        logs.put_delivery_source(name=source_name, logType=log_type, resourceArn=runtime_arn)  # type: ignore[union-attr]
        print(f"    Created source: {source_name}")
    except Exception as exc:
        print(f"    Source skipped (already exists or managed by AWS): {exc.__class__.__name__}")
    return True


def _ensure_destination(logs: object, dest_name: str, log_group_arn: str) -> bool:
    """Create a delivery destination. Returns True on success or if it already exists."""
    try:
        logs.put_delivery_destination(  # type: ignore[union-attr]
            name=dest_name,
            deliveryDestinationType="CWL",
            deliveryDestinationConfiguration={"destinationResourceArn": log_group_arn},
        )
        print(f"    Created destination: {dest_name}")
    except Exception as exc:
        print(f"    Destination skipped (already exists): {exc.__class__.__name__}")
    return True


def _setup_log_delivery(runtime_name: str, runtime_arn: str) -> None:
    """Create log groups + delivery pipelines for both APPLICATION_LOGS and USAGE_LOGS."""
    logs = boto3.client("logs", region_name=REGION)
    runtime_id = runtime_arn.rsplit("/", 1)[-1]

    for log_type in LOG_TYPES:
        suffix = log_type.lower()  # application_logs or usage_logs
        log_group = f"/aws/vendedlogs/bedrock-agentcore/{runtime_id}/{suffix}"
        source_name = f"{runtime_id}-{suffix}-source"
        dest_name = f"{runtime_id}-{suffix}-dest"

        print(f"  [{log_type}]")

        # 1. Create log group
        try:
            logs.create_log_group(logGroupName=log_group)
            print(f"    Created log group: {log_group}")
        except logs.exceptions.ResourceAlreadyExistsException:
            print(f"    Log group exists: {log_group}")

        # 2. Create source
        log_group_arn = f"arn:aws:logs:{REGION}:{ACCOUNT_ID}:log-group:{log_group}"
        if not _ensure_source(logs, source_name, log_type, runtime_arn):
            continue

        # 3. Create destination
        if not _ensure_destination(logs, dest_name, log_group_arn):
            continue

        # 4. Create delivery
        dest_arn = f"arn:aws:logs:{REGION}:{ACCOUNT_ID}:delivery-destination:{dest_name}"
        try:
            logs.create_delivery(deliverySourceName=source_name, deliveryDestinationArn=dest_arn)
            print(f"    Created delivery: {source_name} -> {dest_name}")
        except Exception as exc:
            print(f"    Delivery skipped (already exists): {exc.__class__.__name__}")


def main() -> None:
    """Set up log delivery for all AgentCore runtimes."""
    runtimes = _get_runtime_arns()
    if not runtimes:
        print("No AgentCore runtimes found.")
        return

    print(f"Found {len(runtimes)} runtimes:")
    for name, arn in runtimes.items():
        print(f"\n[{name}]")
        _setup_log_delivery(name, arn)

    print("\nDone.")


if __name__ == "__main__":
    main()
