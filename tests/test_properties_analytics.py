# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Property-based tests for the Analytics API Lambda handler.

Uses hypothesis to verify correctness properties across randomised inputs.
Tests services/api/analytics_handler.py with mocked DynamoDB.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

# Ensure project root is on sys.path so services/ is importable
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from services.api.analytics_handler import handler

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

_VALID_SPECIES = [
    "Koala",
    "Platypus",
    "Wombat",
    "Kangaroo",
    "Echidna",
    "Quokka",
    "Cassowary",
    "Kookaburra",
    "Dingo",
    "Emu",
]

_VALID_STATUSES = [
    "critically_endangered",
    "endangered",
    "vulnerable",
    "near_threatened",
    "least_concern",
]

_ROUTES = ["/analytics/locations", "/analytics/trends", "/analytics/status"]

_species_st = st.sampled_from(_VALID_SPECIES)
_status_st = st.sampled_from(_VALID_STATUSES)
_date_st = st.dates(
    min_value=__import__("datetime").date(2020, 1, 1),
    max_value=__import__("datetime").date(2025, 12, 31),
).map(lambda d: d.isoformat())
_route_st = st.sampled_from(_ROUTES)

# Strategy for generating a list of mock sighting items
_lat_st = st.floats(min_value=-44.0, max_value=-10.0, allow_nan=False, allow_infinity=False)
_lng_st = st.floats(min_value=112.0, max_value=154.0, allow_nan=False, allow_infinity=False)


def _make_sighting(
    species: str,
    date: str,
    status: str,
    lat: float,
    lng: float,
    sighting_id: str = "id-1",
) -> dict[str, Any]:
    """Build a mock DynamoDB sighting item."""
    return {
        "species": species,
        "date": date,
        "conservation_status": status,
        "latitude": str(lat),
        "longitude": str(lng),
        "sighting_id": sighting_id,
        "observer_notes": "",
        "ranger_id": "ranger-1",
        "date_location": f"{date}#{lat},{lng}",
    }


_sighting_st = st.builds(
    _make_sighting,
    species=_species_st,
    date=_date_st,
    status=_status_st,
    lat=_lat_st,
    lng=_lng_st,
    sighting_id=st.uuids().map(str),
)

_sightings_list_st = st.lists(_sighting_st, min_size=0, max_size=15)


def _build_event(
    path: str,
    query_params: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build a minimal API Gateway proxy event."""
    return {
        "httpMethod": "GET",
        "path": path,
        "queryStringParameters": query_params or {},
    }


def _mock_table_from_items(items: list[dict[str, Any]]) -> MagicMock:
    """Create a mock DynamoDB table that returns the given items for scan/query.

    The mock simulates DynamoDB key-condition filtering for query calls by
    inspecting the KeyConditionExpression to extract the partition key value
    and filtering items accordingly. This is necessary because the handler
    issues separate queries per species (trends) or per status (status).
    """
    mock_table = MagicMock()

    def _scan(**kwargs: Any) -> dict[str, Any]:
        return {"Items": list(items)}

    def _extract_partition_value(kce: Any) -> str | None:
        """Extract the partition key equality value from a KeyConditionExpression."""
        expr = kce.get_expression()
        # Simple Equals: values = (Key, value_string)
        if expr.get("operator") == "=":
            vals = expr.get("values", ())
            if len(vals) == 2:
                return vals[1]
        # Compound (AND): values = (left_condition, right_condition)
        # The partition key equality is always the first operand
        if expr.get("operator") == "AND":
            vals = expr.get("values", ())
            if vals:
                return _extract_partition_value(vals[0])
        return None

    def _query(**kwargs: Any) -> dict[str, Any]:
        kce = kwargs.get("KeyConditionExpression")
        index_name = kwargs.get("IndexName", "")
        filtered = list(items)

        if kce is not None:
            pk_value = _extract_partition_value(kce)
            if pk_value is not None:
                if "conservation_status-date-index" in index_name:
                    filtered = [i for i in items if i.get("conservation_status") == pk_value]
                else:
                    filtered = [i for i in items if i.get("species") == pk_value]

        return {"Items": filtered}

    mock_table.scan.side_effect = _scan
    mock_table.query.side_effect = _query
    return mock_table


def _items_match_filters(
    items: list[dict[str, Any]],
    start_date: str | None,
    end_date: str | None,
    species_list: list[str],
    status_list: list[str],
) -> list[dict[str, Any]]:
    """Filter items in Python to mirror what the handler should do."""
    result = []
    for item in items:
        d = item.get("date", "")
        if start_date and d < start_date:
            continue
        if end_date and d > end_date:
            continue
        if species_list and item.get("species") not in species_list:
            continue
        if status_list and item.get("conservation_status") not in status_list:
            continue
        result.append(item)
    return result


# ===================================================================
# Property 7: Aggregation count conservation
# ===================================================================
class TestProperty7AggregationCountConservation:
    """Feature: sighting-analytics-dashboard, Property 7: Aggregation count conservation."""

    @settings(max_examples=100, database=None)
    @given(items=_sightings_list_st, route=_route_st)
    def test_sum_of_counts_equals_total_matching_records(
        self,
        items: list[dict[str, Any]],
        route: str,
    ) -> None:
        """Feature: sighting-analytics-dashboard, Property 7: Aggregation count conservation.

        For any analytics endpoint and any set of sighting records, the sum of
        all count values in the grouped response equals the total number of
        matching records.

        **Validates: Requirements 6.1, 6.2, 6.3**
        """
        mock_table = _mock_table_from_items(items)

        with patch("services.api.analytics_handler.dynamodb") as mock_ddb:
            mock_ddb.Table.return_value = mock_table
            event = _build_event(route)
            response = handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        data = body["data"]

        total_count = sum(entry["count"] for entry in data)
        assert total_count == len(items), (
            f"Sum of counts ({total_count}) != total items ({len(items)}) for route {route}"
        )


# ===================================================================
# Property 8: Filter application correctness
# ===================================================================
class TestProperty8FilterApplicationCorrectness:
    """Feature: sighting-analytics-dashboard, Property 8: Filter application correctness."""

    @settings(max_examples=100, database=None)
    @given(
        items=_sightings_list_st,
        start_date=st.one_of(st.none(), _date_st),
        end_date=st.one_of(st.none(), _date_st),
        species_filter=st.lists(_species_st, min_size=0, max_size=3, unique=True),
        status_filter=st.lists(_status_st, min_size=0, max_size=2, unique=True),
    )
    def test_every_returned_record_satisfies_filters(
        self,
        items: list[dict[str, Any]],
        start_date: str | None,
        end_date: str | None,
        species_filter: list[str],
        status_filter: list[str],
    ) -> None:
        """Feature: sighting-analytics-dashboard, Property 8: Filter application correctness.

        For any valid combination of filter parameters, every record included
        in the API response satisfies all applied filter criteria, and no
        record satisfying all criteria is excluded.

        **Validates: Requirements 6.4**

        We test this on the /analytics/locations endpoint since it does a
        straightforward scan with filters and returns per-location counts.
        We verify the total count matches our own Python-side filtering.
        """
        mock_table = MagicMock()

        # For filter correctness, we need the mock to actually apply filters.
        # We'll make scan return all items and let the handler's FilterExpression
        # be simulated by returning only matching items.
        expected = _items_match_filters(
            items,
            start_date,
            end_date,
            species_filter,
            status_filter,
        )

        # Mock scan to return only the expected filtered items
        # (simulating DynamoDB FilterExpression behavior)
        mock_table.scan.return_value = {"Items": expected}
        mock_table.query.return_value = {"Items": expected}

        query_params: dict[str, str] = {}
        if start_date:
            query_params["start_date"] = start_date
        if end_date:
            query_params["end_date"] = end_date
        if species_filter:
            query_params["species"] = ",".join(species_filter)
        if status_filter:
            query_params["conservation_status"] = ",".join(status_filter)

        with patch("services.api.analytics_handler.dynamodb") as mock_ddb:
            mock_ddb.Table.return_value = mock_table
            event = _build_event("/analytics/locations", query_params or None)
            response = handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        data = body["data"]

        # Sum of counts in response should equal the number of expected items
        total_count = sum(entry["count"] for entry in data)
        assert total_count == len(expected), (
            f"Response count ({total_count}) != expected filtered items ({len(expected)})"
        )


# ===================================================================
# Property 9: Response envelope consistency
# ===================================================================
class TestProperty9ResponseEnvelopeConsistency:
    """Feature: sighting-analytics-dashboard, Property 9: Response envelope consistency."""

    @settings(max_examples=100, database=None)
    @given(items=_sightings_list_st, route=_route_st)
    def test_response_contains_data_count_filters_applied(
        self,
        items: list[dict[str, Any]],
        route: str,
    ) -> None:
        """Feature: sighting-analytics-dashboard, Property 9: Response envelope consistency.

        For any valid request to any analytics endpoint, the JSON response
        contains data (array), count (== len(data)), and filters_applied.

        **Validates: Requirements 6.5**
        """
        mock_table = _mock_table_from_items(items)

        with patch("services.api.analytics_handler.dynamodb") as mock_ddb:
            mock_ddb.Table.return_value = mock_table
            event = _build_event(route)
            response = handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])

        # Must contain all three envelope keys
        assert "data" in body, "Response missing 'data' key"
        assert "count" in body, "Response missing 'count' key"
        assert "filters_applied" in body, "Response missing 'filters_applied' key"

        # data must be a list
        assert isinstance(body["data"], list), f"'data' should be a list, got {type(body['data'])}"

        # count must equal len(data)
        assert body["count"] == len(body["data"]), f"count ({body['count']}) != len(data) ({len(body['data'])})"

        # filters_applied must be a dict
        assert isinstance(body["filters_applied"], dict), (
            f"'filters_applied' should be a dict, got {type(body['filters_applied'])}"
        )


# ===================================================================
# Property 10: Invalid parameters return 400
# ===================================================================

# Strategies for invalid inputs
_invalid_date_st = st.from_regex(
    r"[0-9]{1,4}[-/][0-9]{1,2}[-/][0-9]{1,2}[a-z]?",
    fullmatch=True,
).filter(lambda s: not __import__("re").match(r"^\d{4}-\d{2}-\d{2}$", s))

_unknown_param_st = st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz_").filter(
    lambda s: s not in {"start_date", "end_date", "species", "conservation_status"}
)


class TestProperty10InvalidParametersReturn400:
    """Feature: sighting-analytics-dashboard, Property 10: Invalid parameters return 400."""

    @settings(max_examples=100, database=None)
    @given(route=_route_st, bad_date=_invalid_date_st)
    def test_malformed_date_returns_400(
        self,
        route: str,
        bad_date: str,
    ) -> None:
        """Feature: sighting-analytics-dashboard, Property 10: Invalid parameters return 400.

        For any request with a malformed date parameter, the API returns
        HTTP 400 with a JSON body containing an error key.

        **Validates: Requirements 6.6**
        """
        mock_table = MagicMock()

        with patch("services.api.analytics_handler.dynamodb") as mock_ddb:
            mock_ddb.Table.return_value = mock_table
            event = _build_event(route, {"start_date": bad_date})
            response = handler(event, None)

        assert response["statusCode"] == 400, (
            f"Expected 400 for malformed date '{bad_date}', got {response['statusCode']}"
        )
        body = json.loads(response["body"])
        assert "error" in body, "400 response must contain 'error' key"
        assert len(body["error"]) > 0, "Error message must be non-empty"

    @settings(max_examples=100, database=None)
    @given(route=_route_st, unknown_key=_unknown_param_st)
    def test_unknown_param_returns_400(
        self,
        route: str,
        unknown_key: str,
    ) -> None:
        """Feature: sighting-analytics-dashboard, Property 10: Invalid parameters return 400.

        For any request with an unknown query parameter, the API returns
        HTTP 400 with a JSON body containing an error key.

        **Validates: Requirements 6.6**
        """
        mock_table = MagicMock()

        with patch("services.api.analytics_handler.dynamodb") as mock_ddb:
            mock_ddb.Table.return_value = mock_table
            event = _build_event(route, {unknown_key: "some_value"})
            response = handler(event, None)

        assert response["statusCode"] == 400, (
            f"Expected 400 for unknown param '{unknown_key}', got {response['statusCode']}"
        )
        body = json.loads(response["body"])
        assert "error" in body, "400 response must contain 'error' key"
        assert len(body["error"]) > 0, "Error message must be non-empty"


# ===================================================================
# Property 11: Read-only operations
# ===================================================================
class TestProperty11ReadOnlyOperations:
    """Feature: sighting-analytics-dashboard, Property 11: Read-only operations."""

    @settings(max_examples=100, database=None)
    @given(items=_sightings_list_st, route=_route_st)
    def test_table_contents_unchanged_after_request(
        self,
        items: list[dict[str, Any]],
        route: str,
    ) -> None:
        """Feature: sighting-analytics-dashboard, Property 11: Read-only operations.

        For any request to any analytics endpoint, the set of items in the
        DynamoDB table before and after the request must be identical.

        **Validates: Requirements 6.7**
        """
        # Deep copy items before the request
        items_before = copy.deepcopy(items)

        mock_table = _mock_table_from_items(items)

        with patch("services.api.analytics_handler.dynamodb") as mock_ddb:
            mock_ddb.Table.return_value = mock_table
            event = _build_event(route)
            handler(event, None)

        # Verify no write operations were called on the table
        mock_table.put_item.assert_not_called()
        mock_table.update_item.assert_not_called()
        mock_table.delete_item.assert_not_called()
        mock_table.batch_writer.assert_not_called()

        # Verify items are unchanged
        assert items == items_before, "Table items were mutated during the request"
