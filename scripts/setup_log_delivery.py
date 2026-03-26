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

Idempotent — safe to run multiple times.

Usage:
    AWS_DEFAULT_REGION=us-east-1 python scripts/setup_log_delivery.py
"""

from __future__ import annotations

import boto3

REGION = "us-east-1"
ACCOUNT_ID = boto3.client("sts").get_caller_identity()["Account"]


def _get_runtime_arns() -> dict[str, str]:
    """Discover all AgentCore runtimes and return {name: arn} mapping."""
    client = boto3.client("bedrock-agentcore-control", region_name=REGION)
    resp = client.list_agent_runtimes()
    return {rt["agentRuntimeName"]: rt["agentRuntimeArn"] for rt in resp.get("agentRuntimes", [])}


def _setup_log_delivery(runtime_name: str, runtime_arn: str) -> None:
    """Create log group + delivery pipeline for a single runtime."""
    logs = boto3.client("logs", region_name=REGION)
    runtime_id = runtime_arn.rsplit("/", 1)[-1]
    log_group = f"/aws/vendedlogs/bedrock-agentcore/{runtime_id}"
    source_name = f"{runtime_id}-logs-source"
    dest_name = f"{runtime_id}-logs-dest"

    # 1. Create log group (skip if exists)
    try:
        logs.create_log_group(logGroupName=log_group)
        print(f"  Created log group: {log_group}")
    except logs.exceptions.ResourceAlreadyExistsException:
        print(f"  Log group exists: {log_group}")

    # 2. Create delivery source (skip if exists)
    try:
        logs.put_delivery_source(
            name=source_name,
            logType="APPLICATION_LOGS",
            resourceArn=runtime_arn,
        )
        print(f"  Created delivery source: {source_name}")
    except logs.exceptions.ConflictException:
        print(f"  Delivery source exists: {source_name}")

    # 3. Create delivery destination (skip if exists)
    log_group_arn = f"arn:aws:logs:{REGION}:{ACCOUNT_ID}:log-group:{log_group}"
    try:
        logs.put_delivery_destination(
            name=dest_name,
            deliveryDestinationType="CWL",
            deliveryDestinationConfiguration={
                "destinationResourceArn": log_group_arn,
            },
        )
        print(f"  Created delivery destination: {dest_name}")
    except logs.exceptions.ConflictException:
        print(f"  Delivery destination exists: {dest_name}")

    # 4. Create delivery (skip if exists)
    dest_arn = f"arn:aws:logs:{REGION}:{ACCOUNT_ID}:delivery-destination:{dest_name}"
    try:
        logs.create_delivery(
            deliverySourceName=source_name,
            deliveryDestinationArn=dest_arn,
        )
        print(f"  Created delivery: {source_name} -> {dest_name}")
    except logs.exceptions.ConflictException:
        print(f"  Delivery already exists: {source_name} -> {dest_name}")


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
