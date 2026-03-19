# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""System prompt loader for Bush Ranger AI agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# Default path to the agent configuration file, relative to the project root.
_DEFAULT_CONFIG_PATH = Path("config/agent_config.yaml")


def load_agent_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load the full agent configuration from *config/agent_config.yaml*.

    Args:
        config_path: Optional override for the YAML config file location.

    Returns:
        Parsed YAML configuration as a dictionary.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
    """
    path = config_path or _DEFAULT_CONFIG_PATH
    with open(path, encoding="utf-8") as fh:
        config: dict[str, Any] = yaml.safe_load(fh)
    return config


def load_system_prompt(config_path: Path | None = None) -> str:
    """Load the system prompt string from the agent configuration.

    Args:
        config_path: Optional override for the YAML config file location.

    Returns:
        The system prompt text defined in the configuration.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        KeyError: If the ``system_prompt`` key is missing from the config.
    """
    config = load_agent_config(config_path)
    return str(config["system_prompt"])


def load_model_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load model configuration (primary/secondary IDs, temperature, region).

    Args:
        config_path: Optional override for the YAML config file location.

    Returns:
        Dictionary with ``models`` and ``inference`` sections from the config.
    """
    config = load_agent_config(config_path)
    return {
        "models": config.get("models", {}),
        "inference": config.get("inference", {}),
    }
