# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Strands Agent entry point for Bush Ranger AI on AgentCore Runtime.

Uses BedrockAgentCoreApp to serve the agent via AgentCore's HTTP contract.
Connects to MCP servers hosted on AgentCore via Streamable HTTP transport
using Cognito access tokens obtained via client_credentials grant.
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Any
from urllib.parse import quote

import httpx
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from mcp.client.streamable_http import streamablehttp_client
from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.tools.mcp import MCPClient

try:
    from logging_config import setup_logging
except ModuleNotFoundError:
    from services.shared.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# AgentCore app
# ---------------------------------------------------------------------------
app = BedrockAgentCoreApp()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PRIMARY_MODEL_ID = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
TEMPERATURE = 0.3
REGION = os.environ.get("AWS_REGION", "us-east-1")

SYSTEM_PROMPT = """\
You are Bush Ranger AI, an Australian park ranger assistant specializing in
wildlife tracking, conservation management, and environmental monitoring.

You help park rangers across Australia by:
- Recording and querying wildlife sightings (species, location, conservation status)
- Retrieving conservation documents including species fact sheets, management plans,
  and emergency procedures
- Checking current weather conditions, forecasts, and fire danger assessments
  for Australian locations

You are knowledgeable, helpful, and safety-conscious. When fire danger is elevated,
always prioritise ranger safety and include emergency contact information (000).

Safety guidelines by fire danger level:
- high: Increased vigilance, check fire breaks, ensure comms equipment ready
- very_high: Restrict field activities to essential only, notify base of location
- extreme: Evacuate to safe zones, cease all non-emergency field operations

Data quality rules:
- Coordinates must be within Australia (lat: -44 to -10, lng: 113 to 154)
- Conservation status must be one of: critically_endangered, endangered,
  vulnerable, near_threatened, least_concern
- Sighting dates must not be in the future

At the end of every response, include a brief note listing which tools you used
to gather the information and which MCP server owns them, formatted as:
---
🔧 Tools used: tool_name (server_name), tool_name (server_name)

The MCP server names are:
- wildlife-sightings: create_sighting, query_by_species, query_by_location, query_by_status
- conservation-docs: list_documents, get_document, search_documents
- weather-climate: get_current_weather, get_forecast, assess_fire_danger
"""

# MCP server runtime ARNs (set by CDK as env vars)
WILDLIFE_RUNTIME_ARN = os.environ.get("WILDLIFE_SIGHTINGS_RUNTIME_ARN", "")
DOCS_RUNTIME_ARN = os.environ.get("CONSERVATION_DOCS_RUNTIME_ARN", "")
WEATHER_RUNTIME_ARN = os.environ.get("WEATHER_RUNTIME_ARN", "")

# Cognito M2M credentials (set by CDK as env vars)
COGNITO_TOKEN_URL = os.environ.get("COGNITO_TOKEN_URL", "")
COGNITO_M2M_CLIENT_ID = os.environ.get("COGNITO_M2M_CLIENT_ID", "")
COGNITO_M2M_CLIENT_SECRET = os.environ.get("COGNITO_M2M_CLIENT_SECRET", "")
COGNITO_M2M_SCOPE = os.environ.get("COGNITO_M2M_SCOPE", "mcp/invoke")


# ---------------------------------------------------------------------------
# Cognito client_credentials token retrieval
# ---------------------------------------------------------------------------
_cached_token: str = ""
_token_expiry: float = 0.0


def _get_cognito_access_token() -> str:
    """Obtain a Cognito access token via client_credentials grant.

    Caches the token and refreshes when expired.
    """
    import time  # noqa: PLC0415

    global _cached_token, _token_expiry  # noqa: PLW0603

    now = time.time()
    if _cached_token and now < _token_expiry - 60:
        return _cached_token

    if not COGNITO_TOKEN_URL or not COGNITO_M2M_CLIENT_ID or not COGNITO_M2M_CLIENT_SECRET:
        logger.warning("Cognito M2M credentials not configured, cannot obtain token")
        return ""

    # client_secret_basic: Base64(client_id:client_secret)
    credentials = base64.b64encode(f"{COGNITO_M2M_CLIENT_ID}:{COGNITO_M2M_CLIENT_SECRET}".encode()).decode()

    try:
        resp = httpx.post(
            COGNITO_TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "client_credentials",
                "scope": COGNITO_M2M_SCOPE,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        token_data = resp.json()
        _cached_token = token_data["access_token"]
        _token_expiry = now + token_data.get("expires_in", 3600)
        logger.info("Obtained Cognito M2M access token (expires in %ds)", token_data.get("expires_in", 3600))
        return _cached_token
    except Exception:
        logger.exception("Failed to obtain Cognito M2M access token")
        return ""


# ---------------------------------------------------------------------------
# Helper: build MCP clients for AgentCore-hosted MCP servers
# ---------------------------------------------------------------------------


def _runtime_arn_to_endpoint(arn: str) -> str:
    """Construct the AgentCore invocation URL from a runtime ARN."""
    base = f"https://bedrock-agentcore.{REGION}.amazonaws.com"
    encoded_arn = quote(arn, safe="")
    return f"{base}/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"


def _build_mcp_clients() -> list[MCPClient]:
    """Create MCPClient instances that connect via Streamable HTTP with Cognito auth."""
    clients: list[MCPClient] = []
    endpoints = [
        ("wildlife_sightings", WILDLIFE_RUNTIME_ARN),
        ("conservation_docs", DOCS_RUNTIME_ARN),
        ("weather", WEATHER_RUNTIME_ARN),
    ]

    for name, arn in endpoints:
        if not arn:
            logger.warning("Runtime ARN not configured for %s, skipping", name)
            continue

        mcp_url = _runtime_arn_to_endpoint(arn)

        def _make_transport(endpoint: str = mcp_url) -> Any:  # noqa: E731
            token = _get_cognito_access_token()
            headers: dict[str, str] = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            return streamablehttp_client(endpoint, headers=headers)

        client = MCPClient(_make_transport)
        clients.append(client)

    return clients


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


@app.entrypoint
def invoke(payload: dict[str, Any], context: object) -> dict[str, str]:
    """Handle an invocation from the API Lambda via AgentCore Runtime."""
    user_message = payload.get("prompt", "Hello!")
    location = payload.get("location")

    # Prepend location context so the agent knows where the user is
    if location and isinstance(location, dict):
        lat = location.get("lat")
        lng = location.get("lng")
        if lat is not None and lng is not None:
            user_message = (
                f"[User's current location: lat={lat}, lng={lng}. "
                f"Use these coordinates when the user says 'my area', 'here', or 'near me'.]\n\n"
                f"{user_message}"
            )

    model = BedrockModel(
        model_id=PRIMARY_MODEL_ID,
        temperature=TEMPERATURE,
        region_name=REGION,
    )

    mcp_clients = _build_mcp_clients()

    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=mcp_clients,  # type: ignore[arg-type]
    )

    logger.info("Invoking agent with message: %s", user_message)

    try:
        result = agent(user_message)
        response_text = result.message.get("content", [{}])[0].get("text", str(result))
        return {"result": response_text}
    except Exception:
        logger.exception("Agent invocation failed")
        return {"error": "Agent processing failed"}
    finally:
        for client in mcp_clients:
            try:
                client.__exit__(None, None, None)  # type: ignore[arg-type]
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run()
