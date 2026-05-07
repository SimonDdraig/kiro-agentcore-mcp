# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Unit tests for the Evaluations API Lambda handler.

Tests services/api/evaluations_handler.py with mocked DynamoDB using concrete
fixtures with known data. Complements the property-based tests in
test_properties_evaluations.py.

Requirements: 5.1, 5.2, 5.4
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

# Ensure project root is on sys.path so services/ is importable
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from services.api.evaluations_handler import (
    _handle_recent,
    _handle_summary,
    handler,
)

# ---------------------------------------------------------------------------
# Test fixtures — evaluation results with known evaluators, scores, timestamps
# ---------------------------------------------------------------------------

KNOWN_EVALUATIONS: list[dict[str, Any]] = [
    {
        "invocation_id": "inv-1",
        "evaluator_ts": "Builtin.Helpfulness#2025-06-01T10:00:00Z",
        "evaluator_name": "Builtin.Helpfulness",
        "score": Decimal("0.9"),
        "rationale": "Very helpful response",
        "session_id": "sess-1",
        "prompt_summary": "What animals live near Sydney?",
        "timestamp": "2025-06-01T10:00:00Z",
    },
    {
        "invocation_id": "inv-1",
        "evaluator_ts": "Builtin.ToolSelectionAccuracy#2025-06-01T10:00:00Z",
        "evaluator_name": "Builtin.ToolSelectionAccuracy",
        "score": Decimal("0.8"),
        "rationale": "Good tool usage",
        "session_id": "sess-1",
        "prompt_summary": "What animals live near Sydney?",
        "timestamp": "2025-06-01T10:00:00Z",
    },
    {
        "invocation_id": "inv-2",
        "evaluator_ts": "Builtin.Helpfulness#2025-06-02T14:00:00Z",
        "evaluator_name": "Builtin.Helpfulness",
        "score": Decimal("0.7"),
        "rationale": "Adequate response",
        "session_id": "sess-2",
        "prompt_summary": "Tell me about koalas",
        "timestamp": "2025-06-02T14:00:00Z",
    },
    {
        "invocation_id": "inv-3",
        "evaluator_ts": "BushRangerDomainRules#2025-06-03T09:00:00Z",
        "evaluator_name": "BushRangerDomainRules",
        "score": Decimal("1.0"),
        "rationale": "All domain rules satisfied",
        "session_id": "sess-3",
        "prompt_summary": "Fire danger in Blue Mountains?",
        "timestamp": "2025-06-03T09:00:00Z",
    },
    {
        "invocation_id": "inv-4",
        "evaluator_ts": "Builtin.Helpfulness#2025-06-04T16:00:00Z",
        "evaluator_name": "Builtin.Helpfulness",
        "score": Decimal("0.6"),
        "rationale": "Could be more detailed",
        "session_id": "sess-4",
        "prompt_summary": "Where can I see platypus?",
        "timestamp": "2025-06-04T16:00:00Z",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_event(
    path: str,
    method: str = "GET",
    query_params: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build a minimal API Gateway proxy event."""
    return {
        "httpMethod": method,
        "path": path,
        "queryStringParameters": query_params or {},
    }


def _mock_summary_table(items: list[dict[str, Any]]) -> MagicMock:
    """Create a mock DynamoDB table for summary queries.

    The summary handler queries the GSI per evaluator name, so we filter
    items by evaluator_name to simulate the GSI query behaviour.
    """
    mock_table = MagicMock()

    def _query(**kwargs: Any) -> dict[str, Any]:
        kce = kwargs.get("KeyConditionExpression")
        # Extract the evaluator name from the key condition
        # The handler builds: Key("evaluator_name").eq(name) & ...
        # We match items by evaluator_name
        filtered = list(items)
        if kce is not None:
            expr = kce.get_expression()
            # For simple eq: {'format': ...., 'operator': '=', 'values': (path, value)}
            # For AND: {'operator': 'AND', 'values': (left, right)}
            pk_value = _extract_eq_value(expr)
            if pk_value is not None:
                filtered = [i for i in items if i.get("evaluator_name") == pk_value]
        return {"Items": filtered}

    mock_table.query.side_effect = _query
    return mock_table


def _extract_eq_value(expr: dict[str, Any]) -> str | None:
    """Recursively extract the partition key value from a Key condition expression."""
    op = expr.get("operator")
    if op == "=":
        vals = expr.get("values", ())
        if len(vals) == 2:
            return vals[1]
    if op == "AND":
        vals = expr.get("values", ())
        if vals:
            return _extract_eq_value(vals[0])
    return None


def _mock_recent_table(items: list[dict[str, Any]]) -> MagicMock:
    """Create a mock DynamoDB table for recent/scan queries."""
    mock_table = MagicMock()

    def _scan(**kwargs: Any) -> dict[str, Any]:
        # Apply filter to exclude _POLLER_STATE if present
        filtered = [i for i in items if i.get("invocation_id") != "_POLLER_STATE"]
        return {"Items": filtered}

    mock_table.scan.side_effect = _scan
    return mock_table


def _call_handler(
    path: str,
    method: str = "GET",
    query_params: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Invoke the evaluations handler with mocked DynamoDB."""
    event = _build_event(path, method, query_params)

    if path == "/evaluations/summary":
        mock_table = _mock_summary_table(KNOWN_EVALUATIONS)
    else:
        mock_table = _mock_recent_table(KNOWN_EVALUATIONS)

    with patch("services.api.evaluations_handler.dynamodb") as mock_ddb:
        mock_ddb.Table.return_value = mock_table
        return handler(event, None)


# ===================================================================
# Summary endpoint with no data returns empty array (Req 5.1)
# ===================================================================
class TestSummaryNoData:
    """Verify GET /evaluations/summary with no data returns empty array."""

    def test_returns_empty_data_array(self) -> None:
        """When the table has no evaluation results, data is an empty list."""
        mock_table = _mock_summary_table([])
        result = _handle_summary(
            {"start_date": None, "end_date": None, "limit": 20},
            table=mock_table,
        )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["data"] == []
        assert body["count"] == 0

    def test_response_envelope_format(self) -> None:
        """Empty summary still returns the standard envelope with all keys."""
        mock_table = _mock_summary_table([])
        result = _handle_summary(
            {"start_date": None, "end_date": None, "limit": 20},
            table=mock_table,
        )
        body = json.loads(result["body"])
        assert "data" in body
        assert "count" in body
        assert "filters_applied" in body


# ===================================================================
# Recent endpoint with default limit (Req 5.2)
# ===================================================================
class TestRecentDefaultLimit:
    """Verify GET /evaluations/recent returns up to 20 results by default."""

    def test_returns_all_when_under_limit(self) -> None:
        """With fewer than 20 items, all are returned."""
        mock_table = _mock_recent_table(KNOWN_EVALUATIONS)
        result = _handle_recent(
            {"start_date": None, "end_date": None, "limit": 20},
            table=mock_table,
        )
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["count"] == len(KNOWN_EVALUATIONS)

    def test_respects_default_limit_of_20(self) -> None:
        """When more than 20 items exist, only 20 are returned."""
        # Generate 25 items
        many_items = [
            {
                "invocation_id": f"inv-{i}",
                "evaluator_name": "Builtin.Helpfulness",
                "score": Decimal("0.5"),
                "rationale": "ok",
                "prompt_summary": "test",
                "timestamp": f"2025-06-{i + 1:02d}T10:00:00Z",
            }
            for i in range(25)
        ]
        mock_table = _mock_recent_table(many_items)
        result = _handle_recent(
            {"start_date": None, "end_date": None, "limit": 20},
            table=mock_table,
        )
        body = json.loads(result["body"])
        assert body["count"] == 20

    def test_results_ordered_by_timestamp_descending(self) -> None:
        """Results are sorted with most recent first."""
        mock_table = _mock_recent_table(KNOWN_EVALUATIONS)
        result = _handle_recent(
            {"start_date": None, "end_date": None, "limit": 20},
            table=mock_table,
        )
        body = json.loads(result["body"])
        timestamps = [item["timestamp"] for item in body["data"]]
        assert timestamps == sorted(timestamps, reverse=True)


# ===================================================================
# Routing — handler dispatches to correct function (Req 5.1, 5.2)
# ===================================================================
class TestRouting:
    """Verify the handler routes to the correct handler function based on path."""

    def test_summary_path_returns_200(self) -> None:
        """GET /evaluations/summary routes to the summary handler."""
        response = _call_handler("/evaluations/summary")
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        # Summary returns evaluator-level aggregates (data is a list)
        assert isinstance(body["data"], list)

    def test_recent_path_returns_200(self) -> None:
        """GET /evaluations/recent routes to the recent handler."""
        response = _call_handler("/evaluations/recent")
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert isinstance(body["data"], list)

    def test_unknown_path_returns_404(self) -> None:
        """An unknown path returns 404 with error message."""
        response = _call_handler("/evaluations/unknown")
        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert "error" in body

    def test_options_returns_200_for_cors_preflight(self) -> None:
        """OPTIONS request returns 200 for CORS preflight."""
        response = _call_handler("/evaluations/summary", method="OPTIONS")
        assert response["statusCode"] == 200


# ===================================================================
# CORS headers present on all responses (Req 5.4)
# ===================================================================
class TestCorsHeaders:
    """Verify CORS headers are present on all response types."""

    def _assert_cors_headers(self, response: dict[str, Any]) -> None:
        """Assert that all required CORS headers are present."""
        headers = response.get("headers", {})
        assert "Access-Control-Allow-Origin" in headers
        assert "Access-Control-Allow-Headers" in headers
        assert "Access-Control-Allow-Methods" in headers
        assert "Content-Type" in headers

    def test_cors_on_success_response(self) -> None:
        """CORS headers present on 200 success response."""
        response = _call_handler("/evaluations/summary")
        self._assert_cors_headers(response)

    def test_cors_on_404_response(self) -> None:
        """CORS headers present on 404 error response."""
        response = _call_handler("/evaluations/nonexistent")
        self._assert_cors_headers(response)

    def test_cors_on_400_response(self) -> None:
        """CORS headers present on 400 validation error response."""
        response = _call_handler(
            "/evaluations/summary",
            query_params={"start_date": "bad-date"},
        )
        self._assert_cors_headers(response)

    def test_cors_on_options_preflight(self) -> None:
        """CORS headers present on OPTIONS preflight response."""
        response = _call_handler("/evaluations/summary", method="OPTIONS")
        self._assert_cors_headers(response)
