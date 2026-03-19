# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Unit tests for the Wildlife Sightings MCP server.

Tests services/mcp_servers/wildlife_sightings/server.py with mocked DynamoDB.
Covers create_sighting, query_by_species, query_by_location, query_by_status,
and input validation error handling.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on sys.path so models/ is importable
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from services.mcp_servers.wildlife_sightings.server import (
    create_sighting,
    query_by_location,
    query_by_species,
    query_by_status,
)


@pytest.fixture()
def mock_table() -> MagicMock:
    """Return a MagicMock standing in for a DynamoDB Table resource."""
    return MagicMock()


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------
_PATCH_TARGET = "services.mcp_servers.wildlife_sightings.server._get_table"


def _valid_sighting_kwargs() -> dict[str, Any]:
    """Return keyword arguments for a valid create_sighting call."""
    return {
        "species": "Koala",
        "latitude": -33.8688,
        "longitude": 151.2093,
        "date": "2025-06-15",
        "conservation_status": "vulnerable",
        "observer_notes": "Spotted near eucalyptus grove",
    }


# ===================================================================
# create_sighting
# ===================================================================
class TestCreateSighting:
    """Tests for the create_sighting tool."""

    def test_successful_creation(self, mock_table: MagicMock) -> None:
        """Successful creation returns record with all expected fields."""
        with patch(_PATCH_TARGET, return_value=mock_table):
            result = create_sighting(**_valid_sighting_kwargs())

        assert "sighting_id" in result
        assert result["species"] == "Koala"
        assert result["latitude"] == -33.8688
        assert result["longitude"] == 151.2093
        assert result["date"] == "2025-06-15"
        assert result["conservation_status"] == "vulnerable"
        assert result["observer_notes"] == "Spotted near eucalyptus grove"
        mock_table.put_item.assert_called_once()

    def test_missing_species(self, mock_table: MagicMock) -> None:
        """Missing species returns validation error with 'species' in missing_fields."""
        with patch(_PATCH_TARGET, return_value=mock_table):
            result = create_sighting(
                species=None,
                latitude=-33.8688,
                longitude=151.2093,
                date="2025-06-15",
            )

        assert result["error"] == "validation_error"
        assert "species" in result["missing_fields"]

    def test_missing_latitude(self, mock_table: MagicMock) -> None:
        """Missing latitude returns validation error."""
        with patch(_PATCH_TARGET, return_value=mock_table):
            result = create_sighting(
                species="Koala",
                latitude=None,
                longitude=151.2093,
                date="2025-06-15",
            )

        assert result["error"] == "validation_error"
        assert "latitude" in result["missing_fields"]

    def test_missing_date(self, mock_table: MagicMock) -> None:
        """Missing date returns validation error."""
        with patch(_PATCH_TARGET, return_value=mock_table):
            result = create_sighting(
                species="Koala",
                latitude=-33.8688,
                longitude=151.2093,
                date=None,
            )

        assert result["error"] == "validation_error"
        assert "date" in result["missing_fields"]

    def test_missing_multiple_fields(self, mock_table: MagicMock) -> None:
        """Missing multiple fields returns all missing fields."""
        with patch(_PATCH_TARGET, return_value=mock_table):
            result = create_sighting(
                species=None,
                latitude=None,
                longitude=None,
                date=None,
            )

        assert result["error"] == "validation_error"
        assert set(result["missing_fields"]) == {"species", "latitude", "longitude", "date"}


# ===================================================================
# query_by_species
# ===================================================================
class TestQueryBySpecies:
    """Tests for the query_by_species tool."""

    def test_returns_matching_records(self, mock_table: MagicMock) -> None:
        """Returns matching records for a species."""
        mock_table.query.return_value = {
            "Items": [
                {
                    "sighting_id": "id-1",
                    "species": "Platypus",
                    "latitude": "-37.8",
                    "longitude": "144.9",
                    "date": "2025-06-10",
                    "conservation_status": "near_threatened",
                    "observer_notes": "Swimming in creek",
                },
            ],
        }
        with patch(_PATCH_TARGET, return_value=mock_table):
            result = query_by_species(species="Platypus")

        assert result["count"] == 1
        assert result["sightings"][0]["species"] == "Platypus"

    def test_with_date_range(self, mock_table: MagicMock) -> None:
        """Date range filters are passed to the query."""
        mock_table.query.return_value = {"Items": []}
        with patch(_PATCH_TARGET, return_value=mock_table):
            result = query_by_species(
                species="Koala",
                start_date="2025-01-01",
                end_date="2025-06-30",
            )

        assert result["count"] == 0
        assert result["sightings"] == []
        mock_table.query.assert_called_once()

    def test_returns_empty_list_when_no_matches(self, mock_table: MagicMock) -> None:
        """Returns empty list when no matches found."""
        mock_table.query.return_value = {"Items": []}
        with patch(_PATCH_TARGET, return_value=mock_table):
            result = query_by_species(species="Unicorn")

        assert result["count"] == 0
        assert result["sightings"] == []


# ===================================================================
# query_by_location
# ===================================================================
class TestQueryByLocation:
    """Tests for the query_by_location tool."""

    def _make_item(
        self,
        sighting_id: str,
        lat: float,
        lng: float,
        date: str = "2025-06-15",
    ) -> dict[str, Any]:
        """Build a DynamoDB-style item dict."""
        return {
            "sighting_id": sighting_id,
            "species": "Koala",
            "latitude": str(lat),
            "longitude": str(lng),
            "date": date,
            "conservation_status": "vulnerable",
            "observer_notes": "",
        }

    def test_returns_records_within_radius(self, mock_table: MagicMock) -> None:
        """Records within the radius are returned."""
        # Sydney Opera House ≈ 0 km from query centre
        mock_table.scan.return_value = {
            "Items": [self._make_item("id-1", -33.8568, 151.2153)],
        }
        with patch(_PATCH_TARGET, return_value=mock_table):
            result = query_by_location(
                latitude=-33.8688,
                longitude=151.2093,
                radius_km=5.0,
            )

        assert result["count"] == 1
        assert result["sightings"][0]["sighting_id"] == "id-1"
        assert "distance_km" in result["sightings"][0]

    def test_excludes_records_outside_radius(self, mock_table: MagicMock) -> None:
        """Records outside the radius are excluded."""
        # Melbourne is ~714 km from Sydney
        mock_table.scan.return_value = {
            "Items": [self._make_item("id-far", -37.8136, 144.9631)],
        }
        with patch(_PATCH_TARGET, return_value=mock_table):
            result = query_by_location(
                latitude=-33.8688,
                longitude=151.2093,
                radius_km=5.0,
            )

        assert result["count"] == 0

    def test_with_date_range(self, mock_table: MagicMock) -> None:
        """Date range filters are applied during scan."""
        mock_table.scan.return_value = {
            "Items": [self._make_item("id-1", -33.8568, 151.2153, "2025-03-01")],
        }
        with patch(_PATCH_TARGET, return_value=mock_table):
            result = query_by_location(
                latitude=-33.8688,
                longitude=151.2093,
                radius_km=5.0,
                start_date="2025-01-01",
                end_date="2025-06-30",
            )

        assert result["count"] == 1
        # Verify scan was called with a FilterExpression
        call_kwargs = mock_table.scan.call_args
        assert "FilterExpression" in call_kwargs.kwargs or (
            call_kwargs.args and "FilterExpression" in str(call_kwargs)
        )


# ===================================================================
# query_by_status
# ===================================================================
class TestQueryByStatus:
    """Tests for the query_by_status tool."""

    def test_returns_records_matching_status(self, mock_table: MagicMock) -> None:
        """Returns records matching the conservation status."""
        mock_table.query.return_value = {
            "Items": [
                {
                    "sighting_id": "id-1",
                    "species": "Bilby",
                    "latitude": "-23.7",
                    "longitude": "133.8",
                    "date": "2025-05-20",
                    "conservation_status": "endangered",
                    "observer_notes": "Burrow entrance found",
                },
            ],
        }
        with patch(_PATCH_TARGET, return_value=mock_table):
            result = query_by_status(conservation_status="endangered")

        assert result["count"] == 1
        assert result["sightings"][0]["conservation_status"] == "endangered"
        # Verify GSI was used
        call_kwargs = mock_table.query.call_args
        assert call_kwargs.kwargs.get("IndexName") == "conservation_status-date-index"

    def test_with_date_range(self, mock_table: MagicMock) -> None:
        """Date range filters are applied to the GSI query."""
        mock_table.query.return_value = {"Items": []}
        with patch(_PATCH_TARGET, return_value=mock_table):
            result = query_by_status(
                conservation_status="vulnerable",
                start_date="2025-01-01",
                end_date="2025-12-31",
            )

        assert result["count"] == 0
        assert result["sightings"] == []
        mock_table.query.assert_called_once()
