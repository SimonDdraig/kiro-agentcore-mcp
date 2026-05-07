# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Property-based tests for the Evaluation Poller's log event parser.

Uses hypothesis to verify the parsing round-trip property across randomised
CloudWatch log event inputs.  Tests services/api/evaluation_poller.py.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

# Ensure project root is on sys.path so services/ is importable
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from models.evaluations import PARTITION_KEY, SORT_KEY
from services.api.evaluation_poller import parse_evaluation_event

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_evaluator_names = st.sampled_from(
    [
        "Builtin.Helpfulness",
        "Builtin.ToolSelectionAccuracy",
        "BushRangerDomainRules",
    ]
)

_score_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

_rationale_st = st.text(
    min_size=1,
    max_size=200,
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        blacklist_characters=("\x00",),
    ),
)

_trace_id_st = st.uuids().map(str)
_session_id_st = st.uuids().map(str)

_prompt_summary_st = st.text(
    min_size=0,
    max_size=300,
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        blacklist_characters=("\x00",),
    ),
)

_timestamp_st = st.datetimes(
    min_value=__import__("datetime").datetime(2024, 1, 1),
    max_value=__import__("datetime").datetime(2026, 12, 31),
).map(lambda dt: dt.isoformat())

# Whether to use @message (CloudWatch Insights style) or message key
_message_key_st = st.sampled_from(["@message", "message"])


@st.composite
def _log_event_st(draw: st.DrawFn) -> tuple[dict[str, Any], dict[str, Any]]:
    """Generate a (log_event, expected_fields) pair.

    Returns both the raw CloudWatch log event dict and a dict of the
    expected field values so the test can assert the round-trip.
    """
    evaluator_name = draw(_evaluator_names)
    score = draw(_score_st)
    rationale = draw(_rationale_st)
    trace_id = draw(_trace_id_st)
    session_id = draw(_session_id_st)
    prompt_summary = draw(_prompt_summary_st)
    timestamp = draw(_timestamp_st)
    message_key = draw(_message_key_st)

    body = {
        "evaluator_name": evaluator_name,
        "score": score,
        "rationale": rationale,
        "trace_id": trace_id,
        "session_id": session_id,
        "prompt_summary": prompt_summary,
        "timestamp": timestamp,
    }

    log_event: dict[str, Any] = {message_key: json.dumps(body)}

    expected = {
        "evaluator_name": evaluator_name,
        "score": score,
        "trace_id": trace_id,
        "rationale": rationale,
        "session_id": session_id,
        "prompt_summary": prompt_summary[:200],
        "timestamp": timestamp,
    }

    return log_event, expected


# ===================================================================
# Property 1: Evaluation result parsing round-trip
# ===================================================================
class TestProperty1EvaluationResultParsingRoundTrip:
    """Feature: agentcore-evaluations, Property 1: Evaluation result parsing round-trip."""

    @settings(max_examples=100, database=None)
    @given(data=_log_event_st())
    def test_parsed_item_contains_all_required_attributes(
        self,
        data: tuple[dict[str, Any], dict[str, Any]],
    ) -> None:
        """Feature: agentcore-evaluations, Property 1: Evaluation result parsing round-trip.

        For any valid CloudWatch evaluation result log event containing an
        evaluator name, numeric score (0.0–1.0), rationale string, trace ID,
        and session ID, parsing the log event and building a DynamoDB item
        SHALL produce an item containing all required attributes with values
        matching the original log event data.

        **Validates: Requirements 2.3, 3.4, 4.2**
        """
        log_event, expected = data

        result = parse_evaluation_event(log_event)

        # Must not return None for a valid event
        assert result is not None, f"parse_evaluation_event returned None for valid event: {log_event}"

        # Required DynamoDB attributes must be present
        required_keys = {
            PARTITION_KEY,  # invocation_id
            SORT_KEY,  # evaluator_ts
            "evaluator_name",
            "score",
            "rationale",
            "session_id",
            "prompt_summary",
            "timestamp",
            "ttl",
        }
        assert required_keys.issubset(result.keys()), f"Missing keys: {required_keys - result.keys()}"

        # Values must match the original log event data
        assert result[PARTITION_KEY] == expected["trace_id"], (
            f"invocation_id mismatch: {result[PARTITION_KEY]} != {expected['trace_id']}"
        )
        assert result["evaluator_name"] == expected["evaluator_name"], (
            f"evaluator_name mismatch: {result['evaluator_name']} != {expected['evaluator_name']}"
        )
        assert result["score"] == expected["score"], f"score mismatch: {result['score']} != {expected['score']}"
        assert result["rationale"] == expected["rationale"], (
            f"rationale mismatch: {result['rationale']} != {expected['rationale']}"
        )
        assert result["session_id"] == expected["session_id"], (
            f"session_id mismatch: {result['session_id']} != {expected['session_id']}"
        )
        assert result["prompt_summary"] == expected["prompt_summary"], (
            f"prompt_summary mismatch: {result['prompt_summary']} != {expected['prompt_summary']}"
        )
        assert result["timestamp"] == expected["timestamp"], (
            f"timestamp mismatch: {result['timestamp']} != {expected['timestamp']}"
        )

        # Sort key must be composite: evaluator_name#timestamp
        expected_sort_key = f"{expected['evaluator_name']}#{expected['timestamp']}"
        assert result[SORT_KEY] == expected_sort_key, (
            f"evaluator_ts mismatch: {result[SORT_KEY]} != {expected_sort_key}"
        )

        # TTL must be a positive integer (epoch seconds in the future)
        assert isinstance(result["ttl"], int), f"ttl should be int, got {type(result['ttl'])}"
        assert result["ttl"] > 0, f"ttl should be positive, got {result['ttl']}"


# ===================================================================
# Strategies for Property 2
# ===================================================================

from services.api.evaluations_handler import EVALUATOR_NAMES, _handle_summary


@st.composite
def _evaluation_items_st(draw: st.DrawFn) -> list[dict[str, Any]]:
    """Generate a random set of DynamoDB evaluation result items.

    Each item has an evaluator_name drawn from the known EVALUATOR_NAMES
    and a score in [0.0, 1.0].  The list length varies from 0 to 30.
    """
    num_items = draw(st.integers(min_value=0, max_value=30))
    items: list[dict[str, Any]] = []
    for _ in range(num_items):
        evaluator_name = draw(st.sampled_from(EVALUATOR_NAMES))
        score = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
        items.append(
            {
                "evaluator_name": evaluator_name,
                "score": Decimal(str(score)),
                "invocation_id": draw(st.uuids().map(str)),
                "timestamp": draw(
                    st.datetimes(
                        min_value=__import__("datetime").datetime(2025, 1, 1),
                        max_value=__import__("datetime").datetime(2025, 12, 31),
                    ).map(lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%S"))
                ),
                "rationale": "test",
                "session_id": "sess-1",
                "prompt_summary": "test prompt",
            }
        )
    return items


class _MockTable:
    """A minimal mock of a boto3 DynamoDB Table that supports query()."""

    def __init__(self, items: list[dict[str, Any]]) -> None:
        self._items = items

    def query(self, **kwargs: Any) -> dict[str, Any]:
        """Return items whose evaluator_name matches the key condition.

        This is a simplified mock: it inspects the KeyConditionExpression
        to extract the evaluator name being queried and filters items
        accordingly.  Pagination is not simulated (all items returned in
        one page).
        """
        key_expr = kwargs.get("KeyConditionExpression")
        if key_expr is None:
            return {"Items": []}

        # Extract the evaluator name from the boto3 condition expression.
        # For a compound expression (And), the first value is the Equals
        # condition on evaluator_name.  For a simple Equals, it is the
        # expression itself.
        target_evaluator: str | None = None
        expr_data = key_expr.get_expression()
        values = expr_data.get("values", ())

        for val in values:
            if isinstance(val, str) and val in EVALUATOR_NAMES:
                target_evaluator = val
                break
            # Compound (And) expressions nest sub-expressions in values
            if hasattr(val, "get_expression"):
                sub = val.get_expression()
                for sub_val in sub.get("values", ()):
                    if isinstance(sub_val, str) and sub_val in EVALUATOR_NAMES:
                        target_evaluator = sub_val
                        break
                if target_evaluator:
                    break

        if target_evaluator is None:
            return {"Items": []}

        matched = [item for item in self._items if item.get("evaluator_name") == target_evaluator]
        return {"Items": matched}


# ===================================================================
# Property 2: Summary endpoint computes correct averages
# ===================================================================
class TestProperty2SummaryEndpointAverageComputation:
    """Feature: agentcore-evaluations, Property 2: Summary endpoint computes correct averages."""

    @settings(max_examples=100, database=None)
    @given(items=_evaluation_items_st())
    def test_summary_returns_correct_averages_and_counts(
        self,
        items: list[dict[str, Any]],
    ) -> None:
        """Feature: agentcore-evaluations, Property 2: Summary endpoint computes correct averages.

        For any set of evaluation results in the table with varying evaluator
        names and scores, the /evaluations/summary endpoint SHALL return one
        entry per distinct evaluator where the average_score equals the
        arithmetic mean of all scores for that evaluator within the requested
        time range, and count equals the number of results for that evaluator.

        **Validates: Requirements 5.1**
        """
        # No date filtering — pass None dates so all items are returned
        filters: dict[str, Any] = {
            "start_date": None,
            "end_date": None,
            "limit": 20,
        }

        mock_table = _MockTable(items)
        response = _handle_summary(filters, table=mock_table)

        assert response["statusCode"] == 200

        body = json.loads(response["body"])
        summary_data: list[dict[str, Any]] = body["data"]

        # Build expected averages from the generated items
        from collections import defaultdict

        scores_by_evaluator: dict[str, list[float]] = defaultdict(list)
        for item in items:
            scores_by_evaluator[item["evaluator_name"]].append(float(item["score"]))

        # The summary should have one entry per evaluator that has items
        expected_evaluators = {name for name, scores in scores_by_evaluator.items() if scores}
        actual_evaluators = {entry["evaluator_name"] for entry in summary_data}
        assert actual_evaluators == expected_evaluators, (
            f"Evaluator set mismatch: got {actual_evaluators}, expected {expected_evaluators}"
        )

        # For each evaluator entry, verify average and count
        for entry in summary_data:
            name = entry["evaluator_name"]
            scores = scores_by_evaluator[name]
            expected_count = len(scores)
            expected_avg = round(sum(scores) / len(scores), 4)

            assert entry["count"] == expected_count, (
                f"{name}: count mismatch: got {entry['count']}, expected {expected_count}"
            )
            assert entry["average_score"] == expected_avg, (
                f"{name}: average mismatch: got {entry['average_score']}, expected {expected_avg}"
            )


# ===================================================================
# Strategies for Property 3
# ===================================================================

from services.api.evaluations_handler import _handle_recent


class _MockScanTable:
    """A minimal mock of a boto3 DynamoDB Table that supports scan().

    Used by _handle_recent() which scans the table, filters out
    _POLLER_STATE records, sorts by timestamp descending, and applies
    a limit.
    """

    def __init__(self, items: list[dict[str, Any]]) -> None:
        self._items = items

    def scan(self, **kwargs: Any) -> dict[str, Any]:
        """Return all items, letting the handler do its own filtering.

        The handler applies a FilterExpression to exclude _POLLER_STATE
        records and optionally filter by date range.  This mock applies
        the filter expression if present, otherwise returns all items.
        """
        filter_expr = kwargs.get("FilterExpression")
        if filter_expr is None:
            return {"Items": list(self._items)}

        # Apply the filter expression against each item using boto3's
        # condition expression evaluation is not trivial to replicate,
        # so we do a simple manual filter: exclude _POLLER_STATE items
        # (which is the primary filter the handler always applies).
        filtered = [item for item in self._items if item.get("invocation_id") != "_POLLER_STATE"]
        return {"Items": filtered}


@st.composite
def _recent_items_and_limit_st(
    draw: st.DrawFn,
) -> tuple[list[dict[str, Any]], int]:
    """Generate a random set of evaluation result items and a positive limit.

    Items have unique timestamps to make ordering deterministic.
    Returns (items, limit).
    """
    num_items = draw(st.integers(min_value=0, max_value=30))
    limit = draw(st.integers(min_value=1, max_value=50))

    items: list[dict[str, Any]] = []
    for _ in range(num_items):
        evaluator_name = draw(st.sampled_from(EVALUATOR_NAMES))
        score = draw(
            st.floats(
                min_value=0.0,
                max_value=1.0,
                allow_nan=False,
                allow_infinity=False,
            )
        )
        timestamp = draw(
            st.datetimes(
                min_value=__import__("datetime").datetime(2025, 1, 1),
                max_value=__import__("datetime").datetime(2025, 12, 31),
            ).map(lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%S"))
        )
        items.append(
            {
                "invocation_id": draw(st.uuids().map(str)),
                "evaluator_name": evaluator_name,
                "score": Decimal(str(score)),
                "rationale": "test rationale",
                "session_id": "sess-1",
                "prompt_summary": "test prompt",
                "timestamp": timestamp,
            }
        )
    return items, limit


# ===================================================================
# Property 3: Recent results ordering and limit
# ===================================================================
class TestProperty3RecentResultsOrderingAndLimit:
    """Feature: agentcore-evaluations, Property 3: Recent results ordering and limit."""

    @settings(max_examples=100, database=None)
    @given(data=_recent_items_and_limit_st())
    def test_recent_returns_at_most_limit_results_ordered_by_timestamp_desc(
        self,
        data: tuple[list[dict[str, Any]], int],
    ) -> None:
        """Feature: agentcore-evaluations, Property 3: Recent results ordering and limit.

        For any set of evaluation results in the table and any positive
        integer limit, the /evaluations/recent endpoint SHALL return at most
        `limit` results, ordered by timestamp descending (most recent first),
        and every returned result SHALL have a timestamp greater than or equal
        to any result not returned (i.e., no newer result is omitted while an
        older one is included).

        **Validates: Requirements 5.2**
        """
        items, limit = data

        filters: dict[str, Any] = {
            "start_date": None,
            "end_date": None,
            "limit": limit,
        }

        mock_table = _MockScanTable(items)
        response = _handle_recent(filters, table=mock_table)

        assert response["statusCode"] == 200

        body = json.loads(response["body"])
        results: list[dict[str, Any]] = body["data"]

        # 1. At most `limit` results returned
        assert len(results) <= limit, f"Expected at most {limit} results, got {len(results)}"

        # 2. Results are ordered by timestamp descending
        timestamps = [r["timestamp"] for r in results]
        for i in range(len(timestamps) - 1):
            assert timestamps[i] >= timestamps[i + 1], (
                f"Results not in descending order at index {i}: {timestamps[i]} < {timestamps[i + 1]}"
            )

        # 3. No newer result omitted while an older one is included.
        #    Every returned timestamp must be >= every non-returned timestamp.
        if results and len(items) > len(results):
            returned_timestamps = set(timestamps)
            all_timestamps = sorted([item["timestamp"] for item in items], reverse=True)
            # The returned set should be the top-`limit` timestamps
            # (or all if fewer items than limit).  Specifically: the
            # minimum returned timestamp must be >= the maximum
            # non-returned timestamp.
            non_returned_timestamps = [ts for ts in all_timestamps if ts not in returned_timestamps]
            if non_returned_timestamps:
                min_returned = min(returned_timestamps)
                max_non_returned = max(non_returned_timestamps)
                assert min_returned >= max_non_returned, (
                    f"Newer result omitted: min returned timestamp "
                    f"{min_returned} < max non-returned timestamp "
                    f"{max_non_returned}"
                )


# ===================================================================
# Strategies for Property 4
# ===================================================================

from services.api.evaluations_handler import DATE_PATTERN, _parse_filters


@st.composite
def _invalid_date_string_st(draw: st.DrawFn) -> str:
    r"""Generate a non-empty random string that does NOT match YYYY-MM-DD.

    Uses Hypothesis text strategy and filters out any string that happens
    to match the ``^\d{4}-\d{2}-\d{2}$`` regex.  Empty strings are
    excluded because the handler treats them as "no filter" (equivalent
    to the parameter being absent).
    """
    s = draw(
        st.text(
            min_size=1,
            max_size=30,
            alphabet=st.characters(
                whitelist_categories=("L", "N", "P", "Z", "S"),
                blacklist_characters=("\x00",),
            ),
        ).filter(lambda x: not DATE_PATTERN.match(x))
    )
    return s


# Which date parameter to inject the invalid value into
_date_param_key_st = st.sampled_from(["start_date", "end_date"])


# ===================================================================
# Property 4: Invalid date parameters are rejected
# ===================================================================
class TestProperty4InvalidDateParameterRejection:
    """Feature: agentcore-evaluations, Property 4: Invalid date parameters are rejected."""

    @settings(max_examples=100, database=None)
    @given(
        invalid_date=_invalid_date_string_st(),
        param_key=_date_param_key_st,
    )
    def test_invalid_date_returns_error(
        self,
        invalid_date: str,
        param_key: str,
    ) -> None:
        """Feature: agentcore-evaluations, Property 4: Invalid date parameters are rejected.

        For any string that does not match the ISO-8601 date format
        YYYY-MM-DD, when passed as start_date or end_date to any
        evaluations endpoint, the handler SHALL return a 400 status code
        with a JSON body containing an error field.

        **Validates: Requirements 5.5**
        """
        query_params = {param_key: invalid_date}

        filters, error_message = _parse_filters(query_params)

        # _parse_filters must reject the invalid date with an error
        assert error_message is not None, (
            f"Expected error for invalid {param_key}={invalid_date!r}, but got filters={filters} with no error"
        )

        # The error message should mention the parameter name
        assert param_key in error_message, f"Error message should reference '{param_key}', got: {error_message!r}"
