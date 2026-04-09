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
import uuid
from typing import Any
from urllib.parse import quote

import httpx
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager
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
MEMORY_ID = os.environ.get("MEMORY_ID", "")

SYSTEM_PROMPT = """\
You are Bush Ranger AI, an Australian park ranger assistant specializing in
wildlife tracking, conservation management, and environmental monitoring.

You help park rangers across Australia by:
- Recording and querying wildlife sightings (species, location, conservation status)
- Retrieving conservation documents including species fact sheets, management plans,
  and emergency procedures
- Checking current weather conditions, forecasts, and fire danger assessments
  for Australian locations

Location context rules:
- The user's current GPS coordinates may be included with each request. Treat
  this as a fallback location only.
- If the user has mentioned a specific location or region in the current
  conversation (e.g. "the Pilbara", "Kakadu", "Blue Mountains"), always use
  that location as context for follow-up questions, even if the follow-up
  does not explicitly name the location again.
- Only fall back to the user's GPS coordinates when no location has been
  mentioned or discussed in the conversation.

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

Sighting entry rules:
- If the user does not provide a ranger_id when creating a sighting, you MUST
  ask them for their ranger ID before calling create_sighting. Do not guess or
  omit it.
- If the user refers to dates using relative terms like "today", "yesterday",
  "tomorrow", "last Monday", "two days ago", etc., you MUST resolve them to
  the actual calendar date (YYYY-MM-DD format) before calling any tool. Use
  the current date from the conversation context to calculate the correct date.

"What's nearby?" mode:
When the user asks "what's nearby?", "what's around me?", "anything happening
near me?", or similar proximity questions:
1. Use their GPS coordinates (or the most recently discussed location) to call
   query_by_location with a 25km radius to find recent wildlife sightings
2. Call get_current_weather for the location to get current conditions
3. Call assess_fire_danger for the location
4. Search conservation docs for any alerts relevant to the area
Present the results as a compact ranger dashboard:
- 🦘 Recent sightings (species, distance, date) — highlight any threatened species
- 🌤️ Current weather summary
- 🔥 Fire danger level with safety advice if elevated
- 📋 Any relevant conservation alerts
Keep it scannable and actionable.

Morning briefing mode:
When the user says "morning briefing", "daily briefing", "give me my briefing",
or similar:
1. Call get_forecast for the user's GPS location (3-day forecast)
2. Call assess_fire_danger for the location
3. Call query_by_location with a 50km radius to find sightings from the last 7 days
4. Search conservation docs for current management alerts or seasonal guidance
Present the results as a structured morning briefing:
- ☀️ Today's weather and 3-day outlook
- 🔥 Fire danger assessment with safety actions if elevated
- 🦘 Recent sightings summary in patrol area (last 7 days) — call out any
  threatened species or unusual activity
- 📋 Active conservation notes or seasonal reminders
End with a suggested focus for the day based on the data (e.g. "Quiet week for
sightings in the northern sector — might be worth a patrol up there").

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
# Helper: build memory session manager
# ---------------------------------------------------------------------------


def _build_session_manager(session_id: str, actor_id: str | None) -> AgentCoreMemorySessionManager | None:
    """Create an AgentCoreMemorySessionManager for the given session.

    Returns None (stateless fallback) when MEMORY_ID is not configured
    or when construction fails for any reason.
    """
    if not MEMORY_ID:
        logger.warning("MEMORY_ID not configured, running without memory")
        return None
    try:
        config = AgentCoreMemoryConfig(
            memory_id=MEMORY_ID,
            session_id=session_id,
            actor_id=actor_id or "anonymous",
        )
        return AgentCoreMemorySessionManager(agentcore_memory_config=config, region_name=REGION)
    except Exception:
        logger.exception("Failed to initialize memory session manager")
        return None


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
    session_id = payload.get("session_id", str(uuid.uuid4()))
    actor_id = payload.get("actor_id")

    session_manager = _build_session_manager(session_id, actor_id)

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
        session_manager=session_manager,
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
