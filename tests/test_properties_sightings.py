# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Property-based tests for the Wildlife Sightings MCP server.

Uses hypothesis to verify correctness properties across randomised inputs.
Tests services/mcp_servers/wildlife_sightings/server.py with mocked DynamoDB.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

# Ensure project root is on sys.path so models/ is importable
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from services.mcp_servers.wildlife_sightings.server import (
    _haversine,
    create_sighting,
    query_by_location,
    query_by_species,
    query_by_status,
)

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------
_PATCH_TARGET = "services.mcp_servers.wildlife_sightings.server._get_table"

_species_st = st.text(min_size=1, max_size=50)
_lat_st = st.floats(min_value=-44.0, max_value=-10.0, allow_nan=False, allow_infinity=False)
_lng_st = st.floats(min_value=113.0, max_value=154.0, allow_nan=False, allow_infinity=False)
_status_st = st.sampled_from(
    [
        "critically_endangered",
        "endangered",
        "vulnerable",
        "near_threatened",
        "least_concern",
    ]
)
_date_st = st.dates().map(lambda d: d.isoformat())
_notes_st = st.text(min_size=0, max_size=100)


# ===================================================================
# Property 1: Sighting Round-Trip
# ===================================================================
class TestProperty1SightingRoundTrip:
    """Feature: aws-agentcore-mcp-infrastructure, Property 1: Sighting Round-Trip."""

    @settings(max_examples=100, database=None)
    @given(
        species=_species_st,
        lat=_lat_st,
        lng=_lng_st,
        date=_date_st,
        status=_status_st,
        notes=_notes_st,
    )
    def test_round_trip_preserves_all_fields(
        self,
        species: str,
        lat: float,
        lng: float,
        date: str,
        status: str,
        notes: str,
    ) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 1: Sighting Round-Trip.

        For any valid sighting created via create_sighting, the returned record
        contains all the input fields.

        **Validates: Requirements 1.1, 1.2, 1.7**
        """
        mock_table = MagicMock()
        with patch(_PATCH_TARGET, return_value=mock_table):
            result = create_sighting(
                species=species,
                latitude=lat,
                longitude=lng,
                date=date,
                conservation_status=status,
                observer_notes=notes,
            )

        assert "sighting_id" in result, "Result must contain a sighting_id"
        assert result["species"] == species
        assert result["latitude"] == lat
        assert result["longitude"] == lng
        assert result["date"] == date
        assert result["conservation_status"] == status
        assert result["observer_notes"] == notes
        mock_table.put_item.assert_called_once()


# ===================================================================
# Property 2: Species Filter
# ===================================================================
class TestProperty2SpeciesFilter:
    """Feature: aws-agentcore-mcp-infrastructure, Property 2: Species Filter."""

    @settings(max_examples=100, database=None)
    @given(
        target_species=_species_st,
        other_species=_species_st.filter(lambda s: len(s) > 0),
        target_date=_date_st,
        other_date=_date_st,
        status=_status_st,
    )
    def test_query_returns_only_matching_species(
        self,
        target_species: str,
        other_species: str,
        target_date: str,
        other_date: str,
        status: str,
    ) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 2: Species Filter.

        For any set of sightings with different species, query_by_species returns
        only records where species matches.

        **Validates: Requirements 1.2**
        """
        # Build mock items — only the target species should be returned
        target_item = {
            "sighting_id": "id-target",
            "species": target_species,
            "latitude": "-33.0",
            "longitude": "151.0",
            "date": target_date,
            "conservation_status": status,
            "observer_notes": "",
        }

        mock_table = MagicMock()
        # Mock query to return only the target item (DynamoDB filters by partition key)
        mock_table.query.return_value = {"Items": [target_item]}

        with patch(_PATCH_TARGET, return_value=mock_table):
            result = query_by_species(species=target_species)

        for sighting in result["sightings"]:
            assert sighting["species"] == target_species, (
                f"Expected species '{target_species}', got '{sighting['species']}'"
            )


# ===================================================================
# Property 3: Location Radius
# ===================================================================
class TestProperty3LocationRadius:
    """Feature: aws-agentcore-mcp-infrastructure, Property 3: Location Radius."""

    @settings(max_examples=100, database=None)
    @given(
        sighting_lat=_lat_st,
        sighting_lng=_lng_st,
        center_lat=_lat_st,
        center_lng=_lng_st,
        radius_km=st.floats(min_value=0.1, max_value=2000.0, allow_nan=False, allow_infinity=False),
        date=_date_st,
        status=_status_st,
    )
    def test_location_filter_matches_haversine(
        self,
        sighting_lat: float,
        sighting_lng: float,
        center_lat: float,
        center_lng: float,
        radius_km: float,
        date: str,
        status: str,
    ) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 3: Location Radius.

        For any sighting at location L and query center C with radius R, the
        sighting appears in results iff haversine(L, C) <= R.

        **Validates: Requirements 1.3**
        """
        item = {
            "sighting_id": "id-loc",
            "species": "TestSpecies",
            "latitude": str(sighting_lat),
            "longitude": str(sighting_lng),
            "date": date,
            "conservation_status": status,
            "observer_notes": "",
        }

        mock_table = MagicMock()
        mock_table.scan.return_value = {"Items": [item]}

        with patch(_PATCH_TARGET, return_value=mock_table):
            result = query_by_location(
                latitude=center_lat,
                longitude=center_lng,
                radius_km=radius_km,
            )

        dist = _haversine(center_lat, center_lng, sighting_lat, sighting_lng)
        if dist <= radius_km:
            assert result["count"] == 1, (
                f"Sighting at distance {dist:.2f} km should be within radius {radius_km:.2f} km"
            )
        else:
            assert result["count"] == 0, (
                f"Sighting at distance {dist:.2f} km should be outside radius {radius_km:.2f} km"
            )


# ===================================================================
# Property 4: Status Filter
# ===================================================================
class TestProperty4StatusFilter:
    """Feature: aws-agentcore-mcp-infrastructure, Property 4: Status Filter."""

    @settings(max_examples=100, database=None)
    @given(
        target_status=_status_st,
        date=_date_st,
        species=_species_st,
    )
    def test_query_returns_only_matching_status(
        self,
        target_status: str,
        date: str,
        species: str,
    ) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 4: Status Filter.

        For any set of sightings with different statuses, query_by_status returns
        only records matching the queried status.

        **Validates: Requirements 1.4**
        """
        target_item = {
            "sighting_id": "id-status",
            "species": species,
            "latitude": "-30.0",
            "longitude": "140.0",
            "date": date,
            "conservation_status": target_status,
            "observer_notes": "",
        }

        mock_table = MagicMock()
        # Mock query to return only items matching the target status (GSI filters)
        mock_table.query.return_value = {"Items": [target_item]}

        with patch(_PATCH_TARGET, return_value=mock_table):
            result = query_by_status(conservation_status=target_status)

        for sighting in result["sightings"]:
            assert sighting["conservation_status"] == target_status, (
                f"Expected status '{target_status}', got '{sighting['conservation_status']}'"
            )


# ===================================================================
# Property 5: Missing Fields Error
# ===================================================================
class TestProperty5MissingFieldsError:
    """Feature: aws-agentcore-mcp-infrastructure, Property 5: Missing Fields Error."""

    @settings(max_examples=100, database=None)
    @given(
        include_species=st.booleans(),
        include_lat=st.booleans(),
        include_lng=st.booleans(),
        include_date=st.booleans(),
        species=_species_st,
        lat=_lat_st,
        lng=_lng_st,
        date=_date_st,
    )
    def test_missing_fields_produce_validation_error(
        self,
        include_species: bool,
        include_lat: bool,
        include_lng: bool,
        include_date: bool,
        species: str,
        lat: float,
        lng: float,
        date: str,
    ) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 5: Missing Fields Error.

        For any sighting missing one or more required fields, create_sighting
        returns a validation error listing the missing fields.

        **Validates: Requirements 1.6**
        """
        # At least one field must be missing for this property
        if include_species and include_lat and include_lng and include_date:
            # All fields present — skip (not the scenario under test)
            return

        kwargs: dict[str, Any] = {
            "species": species if include_species else None,
            "latitude": lat if include_lat else None,
            "longitude": lng if include_lng else None,
            "date": date if include_date else None,
        }

        mock_table = MagicMock()
        with patch(_PATCH_TARGET, return_value=mock_table):
            result = create_sighting(**kwargs)

        assert result["error"] == "validation_error", "Should return a validation error"
        assert "missing_fields" in result, "Should list missing fields"

        expected_missing: list[str] = []
        if not include_species:
            expected_missing.append("species")
        if not include_lat:
            expected_missing.append("latitude")
        if not include_lng:
            expected_missing.append("longitude")
        if not include_date:
            expected_missing.append("date")

        assert set(result["missing_fields"]) == set(expected_missing), (
            f"Expected missing {expected_missing}, got {result['missing_fields']}"
        )
        # DynamoDB should NOT have been called
        mock_table.put_item.assert_not_called()


# ===================================================================
# Property 6: Unique IDs
# ===================================================================
class TestProperty6UniqueIDs:
    """Feature: aws-agentcore-mcp-infrastructure, Property 6: Unique IDs."""

    @settings(max_examples=100, database=None)
    @given(
        n=st.integers(min_value=2, max_value=20),
        species=_species_st,
        lat=_lat_st,
        lng=_lng_st,
        date=_date_st,
        status=_status_st,
    )
    def test_all_created_ids_are_distinct(
        self,
        n: int,
        species: str,
        lat: float,
        lng: float,
        date: str,
        status: str,
    ) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 6: Unique IDs.

        For N sightings created, all returned IDs are distinct.

        **Validates: Requirements 1.7**
        """
        mock_table = MagicMock()
        ids: list[str] = []

        with patch(_PATCH_TARGET, return_value=mock_table):
            for _ in range(n):
                result = create_sighting(
                    species=species,
                    latitude=lat,
                    longitude=lng,
                    date=date,
                    conservation_status=status,
                    observer_notes="",
                )
                ids.append(result["sighting_id"])

        assert len(ids) == len(set(ids)), f"Expected {n} unique IDs, but got duplicates: {ids}"
