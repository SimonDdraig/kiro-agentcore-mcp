# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Property-based tests for the API Lambda handler.

Uses Hypothesis to verify Lambda payload passthrough (Property 4).
"""

from __future__ import annotations

import json
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
# Strategies
# ---------------------------------------------------------------------------

# Non-empty text for sessionId / actorId values
_id_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=100,
)

# A simple message string (always non-empty so the handler doesn't 400)
_message_st = st.text(min_size=1, max_size=200).filter(lambda s: s.strip() != "")


# ===================================================================
# Property 4: Lambda payload passthrough
# ===================================================================
class TestProperty4LambdaPayloadPassthrough:
    """Feature: agentcore-short-term-memory, Property 4: Lambda payload passthrough."""

    @settings(max_examples=100, database=None)
    @given(
        message=_message_st,
        session_id=_id_st,
        actor_id=st.one_of(st.none(), _id_st),
    )
    def test_payload_contains_session_and_actor(
        self,
        message: str,
        session_id: str,
        actor_id: str | None,
    ) -> None:
        """# Feature: agentcore-short-term-memory, Property 4: Lambda payload passthrough.

        For any request body containing sessionId and/or actorId fields,
        the API Lambda shall include those same values as session_id and
        actor_id respectively in the agent payload forwarded to AgentCore
        Runtime.

        **Validates: Requirements 3.1, 3.2**
        """
        # Build the request body
        request_body: dict[str, Any] = {"message": message, "sessionId": session_id}
        if actor_id is not None:
            request_body["actorId"] = actor_id

        event: dict[str, Any] = {"body": json.dumps(request_body)}

        # Capture the payload sent to invoke_agent_runtime
        captured_payload: list[dict[str, Any]] = []

        mock_client = MagicMock()

        def _capture_invoke(**kwargs: Any) -> dict[str, Any]:
            raw = kwargs.get("payload", b"{}")
            captured_payload.append(json.loads(raw))
            # Return a minimal successful response
            mock_response_body = MagicMock()
            mock_response_body.read.return_value = json.dumps({"result": "ok"}).encode()
            return {"response": mock_response_body, "contentType": "application/json"}

        mock_client.invoke_agent_runtime = MagicMock(side_effect=_capture_invoke)

        with (
            patch.dict(
                "os.environ",
                {"AGENT_RUNTIME_ARN": "arn:aws:test:us-east-1:123456789012:agent-runtime/test", "CORS_ORIGIN": "*"},
            ),
            patch("services.api.handler.agentcore", mock_client),
        ):
            from services.api.handler import handler

            result = handler(event, None)

        assert result["statusCode"] == 200, f"Expected 200, got {result['statusCode']}: {result['body']}"
        assert len(captured_payload) == 1, "Expected exactly one invoke call"

        payload = captured_payload[0]

        # session_id must match the input sessionId
        assert payload["session_id"] == session_id

        # actor_id must match when provided, must be absent when not provided
        if actor_id is not None:
            assert payload["actor_id"] == actor_id
        else:
            assert "actor_id" not in payload


import uuid


# ===================================================================
# Property 5: Lambda fallback session ID
# ===================================================================
class TestProperty5LambdaFallbackSessionId:
    """Feature: agentcore-short-term-memory, Property 5: Lambda fallback session ID."""

    @settings(max_examples=100, database=None)
    @given(
        message=_message_st,
        actor_id=st.one_of(st.none(), _id_st),
    )
    def test_generates_valid_uuid4_when_session_id_missing(
        self,
        message: str,
        actor_id: str | None,
    ) -> None:
        """# Feature: agentcore-short-term-memory, Property 5: Lambda fallback session ID.

        For any request body that does not contain a sessionId field,
        the API Lambda shall generate a session_id in the agent payload
        that is a valid UUID v4 string.

        **Validates: Requirements 3.3**
        """
        # Build request body WITHOUT sessionId
        request_body: dict[str, Any] = {"message": message}
        if actor_id is not None:
            request_body["actorId"] = actor_id

        event: dict[str, Any] = {"body": json.dumps(request_body)}

        # Capture the payload sent to invoke_agent_runtime
        captured_payload: list[dict[str, Any]] = []

        mock_client = MagicMock()

        def _capture_invoke(**kwargs: Any) -> dict[str, Any]:
            raw = kwargs.get("payload", b"{}")
            captured_payload.append(json.loads(raw))
            mock_response_body = MagicMock()
            mock_response_body.read.return_value = json.dumps({"result": "ok"}).encode()
            return {"response": mock_response_body, "contentType": "application/json"}

        mock_client.invoke_agent_runtime = MagicMock(side_effect=_capture_invoke)

        with (
            patch.dict(
                "os.environ",
                {"AGENT_RUNTIME_ARN": "arn:aws:test:us-east-1:123456789012:agent-runtime/test", "CORS_ORIGIN": "*"},
            ),
            patch("services.api.handler.agentcore", mock_client),
        ):
            from services.api.handler import handler

            result = handler(event, None)

        assert result["statusCode"] == 200, f"Expected 200, got {result['statusCode']}: {result['body']}"
        assert len(captured_payload) == 1, "Expected exactly one invoke call"

        payload = captured_payload[0]

        # session_id must be present and a valid UUID v4
        assert "session_id" in payload, "session_id must be present in payload"
        uuid.UUID(payload["session_id"], version=4)
