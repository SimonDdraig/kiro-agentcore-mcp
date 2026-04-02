# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Unit tests for the Analytics API Lambda handler.

Tests services/api/analytics_handler.py with mocked DynamoDB using concrete
fixtures with known data. Complements the property-based tests in
test_properties_analytics.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on sys.path so services/ is importable
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from services.api.analytics_handler import handler

# ---------------------------------------------------------------------------
# Test fixtures — 5 sightings with known species, dates, locations, statuses
# ---------------------------------------------------------------------------

KNOWN_SIGHTINGS: list[dict[str, Any]] = [
    {
        "sighting_id": "s1",
        "species": "Koala",
        "date": "2025-01-15",
        "conservation_status": "vulnerable",
        "latitude": "-33.7",
        "longitude": "150.3",
        "observer_notes": "Near eucalyptus grove",
        "ranger_id": "ranger-1",
        "date_location": "2025-01-15#-33.7,150.3",
    },
    {
        "sighting_id": "s2",
        "species": "Koala",
        "date": "2025-02-10",
        "conservation_status": "vulnerable",
        "latitude": "-33.8",
        "longitude": "150.4",
        "observer_notes": "Sleeping in tree",
        "ranger_id": "ranger-2",
        "date_location": "2025-02-10#-33.8,150.4",
    },
    {
        "sighting_id": "s3",
        "species": "Platypus",
        "date": "2025-01-20",
        "conservation_status": "near_threatened",
        "latitude": "-37.5",
        "longitude": "144.8",
        "observer_notes": "Swimming in creek",
        "ranger_id": "ranger-1",
        "date_location": "2025-01-20#-37.5,144.8",
    },
    {
        "sighting_id": "s4",
        "species": "Cassowary",
        "date": "2025-03-05",
        "conservation_status": "endangered",
        "latitude": "-16.2",
        "longitude": "145.4",
        "observer_notes": "Crossing road",
        "ranger_id": "ranger-3",
        "date_location": "2025-03-05#-16.2,145.4",
    },
    {
        "sighting_id": "s5",
        "species": "Platypus",
        "date": "2025-03-12",
        "conservation_status": "near_threatened",
        "latitude": "-37.6",
        "longitude": "144.9",
        "observer_notes": "Burrow entrance",
        "ranger_id": "ranger-2",
        "date_location": "2025-03-12#-37.6,144.9",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    """Create a mock DynamoDB table that returns *items* for scan/query.

    Simulates partition-key filtering for query calls so that the handler's
    per-species and per-status queries return the correct subsets.
    """
    mock_table = MagicMock()

    def _scan(**kwargs: Any) -> dict[str, Any]:
        return {"Items": list(items)}

    def _extract_partition_value(kce: Any) -> str | None:
        expr = kce.get_expression()
        if expr.get("operator") == "=":
            vals = expr.get("values", ())
            if len(vals) == 2:
                return vals[1]
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


def _call_handler(
    path: str,
    query_params: dict[str, str] | None = None,
    items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Invoke the analytics handler with a mocked DynamoDB table."""
    if items is None:
        items = KNOWN_SIGHTINGS
    mock_table = _mock_table_from_items(items)
    with patch("services.api.analytics_handler.dynamodb") as mock_ddb:
        mock_ddb.Table.return_value = mock_table
        return handler(_build_event(path, query_params), None)


# ===================================================================
# Location aggregation (Req 6.1)
# ===================================================================
class TestLocationAggregation:
    """Verify GET /analytics/locations groups by rounded lat/lng with correct counts."""

    def test_groups_by_rounded_coordinates(self) -> None:
        """Sightings near the same integer lat/lng are grouped together.

        s1 (-33.7, 150.3) and s2 (-33.8, 150.4) both round to (-34, 150).
        s3 (-37.5, 144.8) and s5 (-37.6, 144.9) both round to (-38, 145).
        s4 (-16.2, 145.4) rounds to (-16, 145).
        Expected: 3 location groups.
        """
        response = _call_handler("/analytics/locations")
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        data = body["data"]

        assert len(data) == 3, f"Expected 3 location groups, got {len(data)}"

    def test_correct_counts_per_location(self) -> None:
        """Each location group has the correct sighting count."""
        response = _call_handler("/analytics/locations")
        body = json.loads(response["body"])
        data = body["data"]

        counts_by_name: dict[str, int] = {}
        for entry in data:
            counts_by_name[entry["locationName"]] = entry["count"]

        # s1 + s2 round to (-34, 150) -> "Blue Mountains NP, NSW"
        assert counts_by_name.get("Blue Mountains NP, NSW") == 2

        # s4 rounds to (-16, 145) -> "Daintree Rainforest, QLD" or "Cape Tribulation, QLD"
        # Both map to (-16, 145) in _KNOWN_LOCATIONS — the dict keeps the last one
        daintree_count = counts_by_name.get("Daintree Rainforest, QLD") or counts_by_name.get("Cape Tribulation, QLD")
        assert daintree_count == 1

    def test_total_count_equals_sighting_count(self) -> None:
        """Sum of all location counts equals total number of sightings."""
        response = _call_handler("/analytics/locations")
        body = json.loads(response["body"])
        total = sum(entry["count"] for entry in body["data"])
        assert total == len(KNOWN_SIGHTINGS)


# ===================================================================
# Trend aggregation (Req 6.2)
# ===================================================================
class TestTrendAggregation:
    """Verify GET /analytics/trends groups by species + month with correct counts."""

    def test_groups_by_species_and_month(self) -> None:
        """With species filter, returns per-species monthly counts.

        Filter for Koala: s1 (2025-01), s2 (2025-02) -> 2 trend entries.
        """
        response = _call_handler("/analytics/trends", {"species": "Koala"})
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        data = body["data"]

        assert len(data) == 2
        months = {entry["month"] for entry in data}
        assert months == {"2025-01", "2025-02"}
        for entry in data:
            assert entry["species"] == "Koala"
            assert entry["count"] == 1

    def test_multiple_species_filter(self) -> None:
        """Filtering for multiple species returns trend lines for each.

        Koala: 2025-01 (1), 2025-02 (1)
        Platypus: 2025-01 (1), 2025-03 (1)
        Total: 4 trend entries.
        """
        response = _call_handler("/analytics/trends", {"species": "Koala,Platypus"})
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        data = body["data"]

        assert len(data) == 4
        species_set = {entry["species"] for entry in data}
        assert species_set == {"Koala", "Platypus"}

    def test_correct_counts_per_species_month(self) -> None:
        """Each species+month bucket has the correct count.

        Platypus in 2025-01: 1 sighting (s3)
        Platypus in 2025-03: 1 sighting (s5)
        """
        response = _call_handler("/analytics/trends", {"species": "Platypus"})
        body = json.loads(response["body"])
        data = body["data"]

        by_month = {entry["month"]: entry["count"] for entry in data}
        assert by_month == {"2025-01": 1, "2025-03": 1}


# ===================================================================
# Aggregated trend with no species filter (Req 3.5)
# ===================================================================
class TestAggregatedTrendNoSpeciesFilter:
    """Verify GET /analytics/trends without species filter returns totals with species='All'."""

    def test_returns_species_all(self) -> None:
        """When no species filter is applied, all entries have species='All'."""
        response = _call_handler("/analytics/trends")
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        data = body["data"]

        for entry in data:
            assert entry["species"] == "All", f"Expected species='All', got '{entry['species']}'"

    def test_aggregated_monthly_totals(self) -> None:
        """Monthly totals aggregate across all species.

        2025-01: s1 (Koala) + s3 (Platypus) = 2
        2025-02: s2 (Koala) = 1
        2025-03: s4 (Cassowary) + s5 (Platypus) = 2
        """
        response = _call_handler("/analytics/trends")
        body = json.loads(response["body"])
        data = body["data"]

        by_month = {entry["month"]: entry["count"] for entry in data}
        assert by_month == {"2025-01": 2, "2025-02": 1, "2025-03": 2}

    def test_total_count_equals_sighting_count(self) -> None:
        """Sum of aggregated monthly counts equals total sightings."""
        response = _call_handler("/analytics/trends")
        body = json.loads(response["body"])
        total = sum(entry["count"] for entry in body["data"])
        assert total == len(KNOWN_SIGHTINGS)


# ===================================================================
# Status aggregation (Req 6.3)
# ===================================================================
class TestStatusAggregation:
    """Verify GET /analytics/status groups by conservation status with correct counts and species."""

    def test_groups_by_status(self) -> None:
        """Returns one entry per conservation status present in the data.

        vulnerable: s1, s2 (Koala)
        near_threatened: s3, s5 (Platypus)
        endangered: s4 (Cassowary)
        Plus empty statuses queried but returning 0 items.
        """
        response = _call_handler("/analytics/status")
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        data = body["data"]

        by_status = {entry["conservation_status"]: entry for entry in data}

        assert by_status["vulnerable"]["count"] == 2
        assert by_status["near_threatened"]["count"] == 2
        assert by_status["endangered"]["count"] == 1

    def test_species_lists_per_status(self) -> None:
        """Each status entry contains the correct sorted species list."""
        response = _call_handler("/analytics/status")
        body = json.loads(response["body"])
        data = body["data"]

        by_status = {entry["conservation_status"]: entry for entry in data}

        assert by_status["vulnerable"]["species"] == ["Koala"]
        assert by_status["near_threatened"]["species"] == ["Platypus"]
        assert by_status["endangered"]["species"] == ["Cassowary"]

    def test_total_count_equals_sighting_count(self) -> None:
        """Sum of all status counts equals total sightings."""
        response = _call_handler("/analytics/status")
        body = json.loads(response["body"])
        total = sum(entry["count"] for entry in body["data"])
        assert total == len(KNOWN_SIGHTINGS)


# ===================================================================
# Invalid date format returns 400 (Req 6.6)
# ===================================================================
class TestInvalidDateFormat:
    """Verify 400 response for invalid date format across all endpoints."""

    @pytest.mark.parametrize(
        "path",
        [
            "/analytics/locations",
            "/analytics/trends",
            "/analytics/status",
        ],
    )
    def test_invalid_start_date(self, path: str) -> None:
        """Malformed start_date returns 400 with error message."""
        response = _call_handler(path, {"start_date": "15-01-2025"})
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
        assert len(body["error"]) > 0

    @pytest.mark.parametrize(
        "path",
        [
            "/analytics/locations",
            "/analytics/trends",
            "/analytics/status",
        ],
    )
    def test_invalid_end_date(self, path: str) -> None:
        """Malformed end_date returns 400 with error message."""
        response = _call_handler(path, {"end_date": "2025/03/01"})
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
        assert len(body["error"]) > 0

    def test_unknown_parameter_returns_400(self) -> None:
        """Unknown query parameter returns 400."""
        response = _call_handler("/analytics/locations", {"foo": "bar"})
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
        assert "foo" in body["error"].lower() or "unknown" in body["error"].lower()
