# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Property-based tests for AgentCore short-term memory integration.

Uses Hypothesis to verify memory config construction (Property 6)
in the agent handler.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

# Ensure project root is on sys.path
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ---------------------------------------------------------------------------
# Mock bedrock_agentcore modules before importing the handler, since the
# package is not installed in the test environment.
# ---------------------------------------------------------------------------

_mock_config_module = MagicMock()
_mock_session_module = MagicMock()


# Make AgentCoreMemoryConfig a real class so we can inspect its attributes
class _FakeMemoryConfig:
    """Stand-in for AgentCoreMemoryConfig that stores kwargs as attributes."""

    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


_mock_config_module.AgentCoreMemoryConfig = _FakeMemoryConfig
_mock_session_module.AgentCoreMemorySessionManager = MagicMock

sys.modules.setdefault("bedrock_agentcore", MagicMock())
sys.modules.setdefault("bedrock_agentcore.memory", MagicMock())
sys.modules.setdefault("bedrock_agentcore.memory.integrations", MagicMock())
sys.modules.setdefault("bedrock_agentcore.memory.integrations.strands", MagicMock())
sys.modules["bedrock_agentcore.memory.integrations.strands.config"] = _mock_config_module
sys.modules["bedrock_agentcore.memory.integrations.strands.session_manager"] = _mock_session_module


# Also mock other handler dependencies that may not be installed.
# Only mock a package if it cannot be imported — using setdefault with a
# MagicMock for packages that *are* installed poisons sys.modules and
# breaks later imports of submodules (e.g. strands.vended_plugins).
def _mock_if_missing(name: str) -> None:
    """Insert a MagicMock into sys.modules only when the real package is absent."""
    try:
        __import__(name)
    except ImportError:
        sys.modules.setdefault(name, MagicMock())


for _mod in [
    "bedrock_agentcore.runtime",
    "mcp",
    "mcp.client",
    "mcp.client.streamable_http",
    "strands",
    "strands.models",
    "strands.models.bedrock",
    "strands.tools",
    "strands.tools.mcp",
    "httpx",
    "logging_config",
]:
    _mock_if_missing(_mod)

from services.agent.handler import _build_session_manager  # noqa: E402

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Non-empty text strings for IDs (memory_id, session_id, actor_id)
_id_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=100,
)

# actor_id can be a string or None
_actor_id_st = st.one_of(st.none(), _id_st)


# ===================================================================
# Property 6: Memory config construction
# ===================================================================
class TestProperty6MemoryConfigConstruction:
    """Feature: agentcore-short-term-memory, Property 6: Memory config construction."""

    @settings(max_examples=100, database=None)
    @given(
        memory_id=_id_st,
        session_id=_id_st,
        actor_id=_actor_id_st,
    )
    def test_config_has_matching_attributes(
        self,
        memory_id: str,
        session_id: str,
        actor_id: str | None,
    ) -> None:
        """Feature: agentcore-short-term-memory, Property 6: Memory config construction.

        For any valid triple of (memory_id, session_id, actor_id),
        _build_session_manager creates an AgentCoreMemoryConfig whose
        memory_id, session_id, and actor_id attributes match the inputs.

        **Validates: Requirements 4.1**
        """
        # Capture the config passed to AgentCoreMemorySessionManager
        captured_config: list[_FakeMemoryConfig] = []

        def _capture_session_manager(agentcore_memory_config: Any = None, **kwargs: Any) -> MagicMock:
            captured_config.append(agentcore_memory_config)
            return MagicMock()

        with (
            patch.dict("os.environ", {"MEMORY_ID": memory_id}),
            patch("services.agent.handler.MEMORY_ID", memory_id),
            patch(
                "services.agent.handler.AgentCoreMemorySessionManager",
                side_effect=_capture_session_manager,
            ),
        ):
            result = _build_session_manager(session_id, actor_id)

        assert result is not None, "Expected a session manager to be returned"
        assert len(captured_config) == 1, "Expected exactly one config to be created"

        config = captured_config[0]
        assert config.memory_id == memory_id
        assert config.session_id == session_id
        expected_actor = actor_id or "anonymous"
        assert config.actor_id == expected_actor
