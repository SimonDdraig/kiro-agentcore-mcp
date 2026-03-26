# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""API Gateway Lambda handler — proxies requests to the AgentCore Runtime."""

import json
import logging
import os
import uuid

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

AGENT_RUNTIME_ARN = os.environ["AGENT_RUNTIME_ARN"]
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")

agentcore = boto3.client("bedrock-agentcore")


def handler(event: dict[str, object], context: object) -> dict[str, object]:
    """Handle POST /invoke from API Gateway."""
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": CORS_ORIGIN,
        "Access-Control-Allow-Headers": "Authorization,Content-Type",
        "Access-Control-Allow-Methods": "POST,OPTIONS",
    }

    try:
        body = json.loads(str(event.get("body") or "{}"))
        message = body.get("message", "")
        if not message:
            return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "Missing 'message' field"})}

        session_id = body.get("sessionId") or str(uuid.uuid4())
        payload = json.dumps({"prompt": message}).encode()

        response = agentcore.invoke_agent_runtime(
            agentRuntimeArn=AGENT_RUNTIME_ARN,
            runtimeSessionId=session_id,
            payload=payload,
        )

        # Collect the streamed response
        content_type = response.get("contentType", "")
        chunks: list[str] = []

        if "text/event-stream" in content_type:
            for line in response["response"].iter_lines(chunk_size=1024):
                if line:
                    decoded = line.decode("utf-8")
                    if decoded.startswith("data: "):
                        chunks.append(decoded[6:])
        else:
            for chunk in response.get("response", []):
                chunks.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk))

        result = "\n".join(chunks) if chunks else "No response from agent."

        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({"response": result, "sessionId": session_id}),
        }

    except Exception:
        logger.exception("Error invoking agent runtime")
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": "Internal server error"}),
        }
