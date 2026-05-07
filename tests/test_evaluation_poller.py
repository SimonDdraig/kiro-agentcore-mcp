# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Unit tests for the Evaluation Poller Lambda handler.

Tests services/api/evaluation_poller.py with mocked boto3 clients.
Complements the property-based tests in test_properties_evaluations.py.

Requirements: 1.3, 4.1
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

# Ensure project root is on sys.path so services/ is importable
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from models.evaluations import PARTITION_KEY, SORT_KEY
from services.api.evaluation_poller import (
    POLLER_STATE_PK,
    POLLER_STATE_SK,
    handler,
    parse_evaluation_event,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_log_event(
    evaluator_name: str = "Builtin.Helpfulness",
    score: float = 0.85,
    trace_id: str = "trace-001",
    rationale: str = "Good response",
    session_id: str = "session-001",
    prompt_summary: str = "What animals live here?",
    timestamp: str = "2025-06-01T12:00:00Z",
) -> dict[str, Any]:
    """Build a valid CloudWatch log event dict."""
    body = {
        "evaluator_name": evaluator_name,
        "score": score,
        "trace_id": trace_id,
        "rationale": rationale,
        "session_id": session_id,
        "prompt_summary": prompt_summary,
        "timestamp": timestamp,
    }
    return {"@message": json.dumps(body)}


# ===================================================================
# Test: Empty CloudWatch response (Req 1.3)
# ===================================================================


class TestEmptyCloudWatchResponse:
    """Poller handles empty CloudWatch response — no new events."""

    def test_handler_returns_zero_processed(self) -> None:
        """When CloudWatch returns no events, handler reports 0 processed."""
        mock_table = MagicMock()
        mock_table.table_name = "BushRangerEvaluations"
        # get_item returns no existing state → uses default epoch
        mock_table.get_item.return_value = {}

        with (
            patch("services.api.evaluation_poller.dynamodb") as mock_ddb,
            patch("services.api.evaluation_poller.logs_client") as mock_logs,
            patch("services.api.evaluation_poller.RESULTS_LOG_GROUP", "test-log-group"),
        ):
            mock_ddb.Table.return_value = mock_table

            # CloudWatch query returns empty results
            mock_logs.start_query.return_value = {"queryId": "q-123"}
            mock_logs.get_query_results.return_value = {
                "status": "Complete",
                "results": [],
            }

            result = handler({}, None)

        assert result["processed"] == 0
        assert result["statusCode"] == 200
        # Should NOT attempt batch writes or state updates
        mock_table.put_item.assert_not_called()

    def test_handler_returns_no_new_events_message(self) -> None:
        """When CloudWatch returns no events, handler includes descriptive message."""
        mock_table = MagicMock()
        mock_table.table_name = "BushRangerEvaluations"
        mock_table.get_item.return_value = {}

        with (
            patch("services.api.evaluation_poller.dynamodb") as mock_ddb,
            patch("services.api.evaluation_poller.logs_client") as mock_logs,
            patch("services.api.evaluation_poller.RESULTS_LOG_GROUP", "test-log-group"),
        ):
            mock_ddb.Table.return_value = mock_table
            mock_logs.start_query.return_value = {"queryId": "q-123"}
            mock_logs.get_query_results.return_value = {
                "status": "Complete",
                "results": [],
            }

            result = handler({}, None)

        assert "No new events" in result.get("message", "")


# ===================================================================
# Test: Malformed log event handling (Req 1.3)
# ===================================================================


class TestMalformedLogEvent:
    """Poller handles malformed log events — skips and logs warning."""

    def test_missing_message_field_returns_none(self) -> None:
        """A log event with no @message or message field is skipped."""
        result = parse_evaluation_event({"some_other_field": "value"})
        assert result is None

    def test_missing_required_fields_returns_none(self) -> None:
        """A log event missing evaluator_name, score, or trace_id is skipped."""
        # Missing score and trace_id
        event = {"@message": json.dumps({"evaluator_name": "Test"})}
        result = parse_evaluation_event(event)
        assert result is None

    def test_invalid_json_message_returns_none(self) -> None:
        """A log event with non-JSON @message is skipped."""
        result = parse_evaluation_event({"@message": "not valid json {{"})
        assert result is None

    def test_score_out_of_range_returns_none(self) -> None:
        """A log event with score outside [0.0, 1.0] is skipped."""
        event = {
            "@message": json.dumps(
                {
                    "evaluator_name": "Test",
                    "score": 1.5,
                    "trace_id": "t-1",
                }
            )
        }
        result = parse_evaluation_event(event)
        assert result is None

    def test_handler_skips_malformed_and_processes_valid(self) -> None:
        """Handler skips malformed events but still processes valid ones."""
        malformed_row = [{"field": "@message", "value": "bad json {{"}]
        valid_body = json.dumps(
            {
                "evaluator_name": "Builtin.Helpfulness",
                "score": 0.9,
                "trace_id": "trace-ok",
                "rationale": "Good",
                "session_id": "sess-1",
                "prompt_summary": "Hello",
                "timestamp": "2025-06-01T12:00:00Z",
            }
        )
        valid_row = [
            {"field": "@timestamp", "value": "2025-06-01T12:00:00Z"},
            {"field": "@message", "value": valid_body},
        ]

        mock_table = MagicMock()
        mock_table.table_name = "BushRangerEvaluations"
        mock_table.get_item.return_value = {}

        mock_batch_client = MagicMock()
        mock_batch_client.batch_write_item.return_value = {"UnprocessedItems": {}}

        with (
            patch("services.api.evaluation_poller.dynamodb") as mock_ddb,
            patch("services.api.evaluation_poller.logs_client") as mock_logs,
            patch("services.api.evaluation_poller.RESULTS_LOG_GROUP", "test-log-group"),
        ):
            mock_ddb.Table.return_value = mock_table
            mock_ddb.meta.client = mock_batch_client

            mock_logs.start_query.return_value = {"queryId": "q-456"}
            mock_logs.get_query_results.return_value = {
                "status": "Complete",
                "results": [malformed_row, valid_row],
            }

            result = handler({}, None)

        assert result["processed"] == 1
        assert result["skipped"] == 1


# ===================================================================
# Test: Poller state update (Req 4.1)
# ===================================================================


class TestPollerStateUpdate:
    """Poller updates _POLLER_STATE control record after successful processing."""

    def test_updates_state_after_processing(self) -> None:
        """After processing events, the control record is updated with the latest timestamp."""
        valid_body = json.dumps(
            {
                "evaluator_name": "Builtin.Helpfulness",
                "score": 0.75,
                "trace_id": "trace-100",
                "rationale": "Decent",
                "session_id": "sess-100",
                "prompt_summary": "Tell me about koalas",
                "timestamp": "2025-06-15T10:30:00Z",
            }
        )
        valid_row = [
            {"field": "@timestamp", "value": "2025-06-15T10:30:00Z"},
            {"field": "@message", "value": valid_body},
        ]

        mock_table = MagicMock()
        mock_table.table_name = "BushRangerEvaluations"
        # Simulate existing state
        mock_table.get_item.return_value = {
            "Item": {
                PARTITION_KEY: POLLER_STATE_PK,
                SORT_KEY: POLLER_STATE_SK,
                "last_processed_ts": "2025-06-15T09:00:00Z",
            }
        }

        mock_batch_client = MagicMock()
        mock_batch_client.batch_write_item.return_value = {"UnprocessedItems": {}}

        with (
            patch("services.api.evaluation_poller.dynamodb") as mock_ddb,
            patch("services.api.evaluation_poller.logs_client") as mock_logs,
            patch("services.api.evaluation_poller.RESULTS_LOG_GROUP", "test-log-group"),
        ):
            mock_ddb.Table.return_value = mock_table
            mock_ddb.meta.client = mock_batch_client

            mock_logs.start_query.return_value = {"queryId": "q-789"}
            mock_logs.get_query_results.return_value = {
                "status": "Complete",
                "results": [valid_row],
            }

            handler({}, None)

        # Verify put_item was called with the updated state record
        mock_table.put_item.assert_called_once()
        call_kwargs = mock_table.put_item.call_args
        item = call_kwargs[1]["Item"] if "Item" in call_kwargs[1] else call_kwargs[0][0]
        assert item[PARTITION_KEY] == POLLER_STATE_PK
        assert item[SORT_KEY] == POLLER_STATE_SK
        assert item["last_processed_ts"] == "2025-06-15T10:30:00Z"

    def test_does_not_update_state_when_no_events(self) -> None:
        """When no events are processed, the control record is NOT updated."""
        mock_table = MagicMock()
        mock_table.table_name = "BushRangerEvaluations"
        mock_table.get_item.return_value = {}

        with (
            patch("services.api.evaluation_poller.dynamodb") as mock_ddb,
            patch("services.api.evaluation_poller.logs_client") as mock_logs,
            patch("services.api.evaluation_poller.RESULTS_LOG_GROUP", "test-log-group"),
        ):
            mock_ddb.Table.return_value = mock_table
            mock_logs.start_query.return_value = {"queryId": "q-000"}
            mock_logs.get_query_results.return_value = {
                "status": "Complete",
                "results": [],
            }

            handler({}, None)

        mock_table.put_item.assert_not_called()
