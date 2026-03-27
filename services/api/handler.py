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
        agent_payload: dict[str, object] = {"prompt": message}
        location = body.get("location")
        if location:
            agent_payload["location"] = location
        payload = json.dumps(agent_payload).encode()

        response = agentcore.invoke_agent_runtime(
            agentRuntimeArn=AGENT_RUNTIME_ARN,
            runtimeSessionId=session_id,
            payload=payload,
        )

        # Read the full response body
        raw = response["response"].read()
        result = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)

        logger.info("content_type=%s, result_len=%d", response.get("contentType", ""), len(result))
        logger.info("result_first200=%s", repr(result[:200]))

        # The agent returns JSON like '{"result": "..."}' — extract the text
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict) and "result" in parsed:
                result = parsed["result"]
        except (json.JSONDecodeError, TypeError):
            pass

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
