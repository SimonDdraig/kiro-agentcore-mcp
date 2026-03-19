# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Strands Agent entry point for Bush Ranger AI.

Connects to four MCP servers via AgentCore and uses Claude Sonnet as the
primary reasoning model with Claude Haiku available for lighter tasks.
"""

from __future__ import annotations

import logging

from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.tools.mcp import MCPClient
from strands_tools import AgentSkills

from services.agent.prompts import load_model_config, load_system_prompt
from services.agent.steering.data_quality import data_quality_handler
from services.agent.steering.safety import safety_handler

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MCP server names as registered in AgentCore
# ---------------------------------------------------------------------------
MCP_SERVER_WILDLIFE_SIGHTINGS = "wildlife_sightings"
MCP_SERVER_CONSERVATION_DOCS = "conservation_docs"
MCP_SERVER_WEATHER = "weather"
MCP_SERVER_FETCH = "fetch_server"

ALL_MCP_SERVERS = [
    MCP_SERVER_WILDLIFE_SIGHTINGS,
    MCP_SERVER_CONSERVATION_DOCS,
    MCP_SERVER_WEATHER,
    MCP_SERVER_FETCH,
]


def _build_bedrock_model(model_id: str, temperature: float, region: str) -> BedrockModel:
    """Create a Bedrock model instance for the given model ID.

    Args:
        model_id: Amazon Bedrock model identifier.
        temperature: Sampling temperature.
        region: AWS region for the Bedrock endpoint.

    Returns:
        Configured ``BedrockModel`` instance.
    """
    return BedrockModel(
        model_id=model_id,
        temperature=temperature,
        region_name=region,
    )


def _build_mcp_clients() -> list[MCPClient]:
    """Create MCP client connections for all four AgentCore MCP servers.

    Returns:
        List of ``MCPClient`` instances, one per MCP server.
    """
    clients: list[MCPClient] = []
    for server_name in ALL_MCP_SERVERS:
        client = MCPClient(server_name=server_name)  # type: ignore[call-arg]
        clients.append(client)
    return clients


def create_primary_agent() -> Agent:
    """Create the primary Bush Ranger AI agent (Claude Sonnet).

    The agent is wired to all four MCP servers via AgentCore and configured
    with the AgentSkills plugin plus both LLMSteeringHandler plugins for
    data quality and safety.

    Returns:
        Fully configured ``Agent`` instance ready to handle requests.
    """
    system_prompt = load_system_prompt()
    model_config = load_model_config()

    primary_model_id: str = model_config["models"]["primary"]["model_id"]
    temperature: float = float(model_config["inference"]["temperature"])
    region: str = str(model_config["inference"]["region"])

    model = _build_bedrock_model(primary_model_id, temperature, region)
    mcp_clients = _build_mcp_clients()

    # AgentSkills plugin — loads skill definitions from ./skills/ on demand
    skills_plugin = AgentSkills(skills="./skills/")

    agent = Agent(
        model=model,
        system_prompt=system_prompt,
        tools=mcp_clients,  # type: ignore[arg-type]
        plugins=[skills_plugin, data_quality_handler, safety_handler],
    )

    logger.info(
        "Primary agent created with model=%s, temperature=%s, region=%s",
        primary_model_id,
        temperature,
        region,
    )
    return agent


def create_secondary_agent() -> Agent:
    """Create the secondary Bush Ranger AI agent (Claude Haiku).

    Used for lighter classification, summarisation, and formatting tasks
    to minimise per-invocation model costs.

    Returns:
        Configured ``Agent`` instance using the Haiku model.
    """
    system_prompt = load_system_prompt()
    model_config = load_model_config()

    secondary_model_id: str = model_config["models"]["secondary"]["model_id"]
    temperature: float = float(model_config["inference"]["temperature"])
    region: str = str(model_config["inference"]["region"])

    model = _build_bedrock_model(secondary_model_id, temperature, region)
    mcp_clients = _build_mcp_clients()

    agent = Agent(
        model=model,
        system_prompt=system_prompt,
        tools=mcp_clients,  # type: ignore[arg-type]
    )

    logger.info(
        "Secondary agent created with model=%s, temperature=%s, region=%s",
        secondary_model_id,
        temperature,
        region,
    )
    return agent
