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
from hypothesis import given, settings
from hypothesis import strategies as st

# Ensure project root is on sys.path so models/ is importable
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from models.rangers import RangerRecord
from scripts.seed_sightings import RANGERS, generate_sightings
from services.mcp_servers.wildlife_sightings.server import (
    _record_to_dict,
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
        assert "FilterExpression" in call_kwargs.kwargs or (call_kwargs.args and "FilterExpression" in str(call_kwargs))


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


# ===================================================================
# ranger_id behavior (Task 7.1)
# ===================================================================


class TestRangerIdBehavior:
    """Tests for ranger_id field across create, query, and legacy paths."""

    def test_create_sighting_with_ranger_id(self, mock_table: MagicMock) -> None:
        """ranger_id is stored in DynamoDB and returned when provided."""
        with patch(_PATCH_TARGET, return_value=mock_table):
            result = create_sighting(**_valid_sighting_kwargs(), ranger_id="ranger-007")

        assert result["ranger_id"] == "ranger-007"
        # Verify the item written to DynamoDB contains ranger_id
        put_item_kwargs = mock_table.put_item.call_args
        assert put_item_kwargs.kwargs["Item"]["ranger_id"] == "ranger-007"

    def test_create_sighting_without_ranger_id(self, mock_table: MagicMock) -> None:
        """ranger_id defaults to empty string when not provided."""
        with patch(_PATCH_TARGET, return_value=mock_table):
            result = create_sighting(**_valid_sighting_kwargs())

        assert result["ranger_id"] == ""
        put_item_kwargs = mock_table.put_item.call_args
        assert put_item_kwargs.kwargs["Item"]["ranger_id"] == ""

    def test_record_to_dict_legacy_item(self) -> None:
        """Legacy DynamoDB items without ranger_id get default empty string."""
        legacy_item: dict[str, Any] = {
            "sighting_id": "abc-123",
            "species": "Koala",
            "latitude": "-33.87",
            "longitude": "151.21",
            "date": "2025-01-01",
            "conservation_status": "vulnerable",
            "observer_notes": "Old record",
            # no ranger_id key at all
        }
        result = _record_to_dict(legacy_item)
        assert result["ranger_id"] == ""

    def test_ranger_record_dataclass(self) -> None:
        """RangerRecord has all required fields with correct types."""
        ranger = RangerRecord(
            ranger_id="ranger-001",
            name="Test Ranger",
            email="test@example.com",
            region="Blue Mountains NP, NSW",
            phone="+61 2 0000 0000",
            active=True,
            start_date="2020-01-01",
        )
        assert ranger.ranger_id == "ranger-001"
        assert ranger.name == "Test Ranger"
        assert ranger.email == "test@example.com"
        assert ranger.region == "Blue Mountains NP, NSW"
        assert ranger.phone == "+61 2 0000 0000"
        assert ranger.active is True
        assert ranger.start_date == "2020-01-01"

    def test_sample_rangers_count(self) -> None:
        """Seed script defines at least 10 sample rangers."""
        assert len(RANGERS) >= 10


# ===================================================================
# Property 1: Ranger ID round-trip through create_sighting
# ===================================================================

# Shared strategies for property tests
_species_st = st.text(min_size=1, max_size=50)
_lat_st = st.floats(min_value=-44.0, max_value=-10.0, allow_nan=False, allow_infinity=False)
_lng_st = st.floats(min_value=113.0, max_value=154.0, allow_nan=False, allow_infinity=False)
_status_st = st.sampled_from(["critically_endangered", "endangered", "vulnerable", "near_threatened", "least_concern"])
_date_st = st.dates().map(lambda d: d.isoformat())
_notes_st = st.text(min_size=0, max_size=100)
_ranger_id_st = st.text(min_size=1, max_size=50)


@settings(max_examples=100, database=None)
@given(
    species=_species_st,
    lat=_lat_st,
    lng=_lng_st,
    date=_date_st,
    status=_status_st,
    notes=_notes_st,
    ranger_id=_ranger_id_st,
)
def test_property_ranger_id_round_trip_through_create_sighting(
    species: str,
    lat: float,
    lng: float,
    date: str,
    status: str,
    notes: str,
    ranger_id: str,
) -> None:
    """Feature: ranger-id-field, Property 1: Ranger ID round-trip through create_sighting.

    For any valid sighting parameters and any non-empty string ranger_id,
    calling create_sighting stores the ranger_id in the DynamoDB put_item
    call and returns it in the response dict.

    **Validates: Requirements 2.2, 2.4**
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
            ranger_id=ranger_id,
        )

    # Assert put_item was called and the Item contains the ranger_id
    mock_table.put_item.assert_called_once()
    put_item_kwargs = mock_table.put_item.call_args
    assert put_item_kwargs.kwargs["Item"]["ranger_id"] == ranger_id, (
        f"Expected ranger_id '{ranger_id}' in DynamoDB item, got '{put_item_kwargs.kwargs['Item'].get('ranger_id')}'"
    )

    # Assert the response dict contains the same ranger_id
    assert result["ranger_id"] == ranger_id, (
        f"Expected ranger_id '{ranger_id}' in response, got '{result.get('ranger_id')}'"
    )


# ===================================================================
# Property 2: Create response always contains ranger_id
# ===================================================================

# Strategy that optionally includes or excludes ranger_id
_optional_ranger_id_st = st.one_of(st.just(""), st.text(min_size=1, max_size=50))


@settings(max_examples=100, database=None)
@given(
    species=_species_st,
    lat=_lat_st,
    lng=_lng_st,
    date=_date_st,
    status=_status_st,
    notes=_notes_st,
    ranger_id=_optional_ranger_id_st,
)
def test_property_create_response_always_contains_ranger_id(
    species: str,
    lat: float,
    lng: float,
    date: str,
    status: str,
    notes: str,
    ranger_id: str,
) -> None:
    """Feature: ranger-id-field, Property 2: Create response always contains ranger_id.

    For any valid sighting parameters (with or without an explicit ranger_id),
    the dict returned by create_sighting should always contain a ranger_id key
    whose value is a string.

    **Validates: Requirements 2.4, 2.3**
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
            ranger_id=ranger_id,
        )

    # Assert the response always contains ranger_id as a string
    assert "ranger_id" in result, "Response dict must always contain 'ranger_id' key"
    assert isinstance(result["ranger_id"], str), (
        f"Expected ranger_id to be str, got {type(result['ranger_id']).__name__}"
    )


# ===================================================================
# Property 3: Record-to-dict always includes ranger_id
# ===================================================================


@settings(max_examples=100, database=None)
@given(
    sighting_id=st.text(min_size=1, max_size=50),
    species=_species_st,
    lat=_lat_st,
    lng=_lng_st,
    date=_date_st,
    status=_status_st,
    notes=_notes_st,
    include_ranger=st.booleans(),
    ranger_id=_optional_ranger_id_st,
)
def test_property_record_to_dict_always_includes_ranger_id(
    sighting_id: str,
    species: str,
    lat: float,
    lng: float,
    date: str,
    status: str,
    notes: str,
    include_ranger: bool,
    ranger_id: str,
) -> None:
    """Feature: ranger-id-field, Property 3: Record-to-dict always includes ranger_id.

    For any DynamoDB item dict (whether or not it contains a ranger_id attribute),
    converting it via _record_to_dict should produce an output dict that contains
    a ranger_id key with a string value. If the input item has a ranger_id, the
    output should match it; if the input item lacks ranger_id, the output should
    default to "".

    **Validates: Requirements 3.1, 3.2**
    """
    item: dict[str, Any] = {
        "sighting_id": sighting_id,
        "species": species,
        "latitude": str(lat),
        "longitude": str(lng),
        "date": date,
        "conservation_status": status,
        "observer_notes": notes,
    }

    if include_ranger:
        item["ranger_id"] = ranger_id

    result = _record_to_dict(item)

    # Output must always contain ranger_id as a string
    assert "ranger_id" in result, "Output dict must always contain 'ranger_id' key"
    assert isinstance(result["ranger_id"], str), (
        f"Expected ranger_id to be str, got {type(result['ranger_id']).__name__}"
    )

    # If input had ranger_id, output must match; otherwise default to ""
    if include_ranger:
        assert result["ranger_id"] == ranger_id, (
            f"Expected ranger_id '{ranger_id}' in output, got '{result['ranger_id']}'"
        )
    else:
        assert result["ranger_id"] == "", f"Expected empty string for missing ranger_id, got '{result['ranger_id']}'"


# ===================================================================
# Property 4: Seed sighting ranger_ids are from the valid ranger set
# ===================================================================

# Pre-generate the sightings list once (deterministic after seed script logic)
_SEED_SIGHTINGS = generate_sightings()
_VALID_RANGER_IDS = {r["ranger_id"] for r in RANGERS}


@settings(max_examples=100, database=None)
@given(index=st.integers(min_value=0, max_value=999))
def test_property_seed_sighting_ranger_ids_from_valid_set(index: int) -> None:
    """Feature: ranger-id-field, Property 4: Seed sighting ranger_ids are from the valid ranger set.

    For any sighting record generated by the seed script, the ranger_id value
    should be a member of the set of ranger_id values defined in the sample
    rangers list.

    **Validates: Requirements 5.3, 5.4**
    """
    sighting = _SEED_SIGHTINGS[index]
    assert sighting["ranger_id"] in _VALID_RANGER_IDS, (
        f"Sighting at index {index} has ranger_id '{sighting['ranger_id']}' "
        f"which is not in the valid ranger set: {_VALID_RANGER_IDS}"
    )
