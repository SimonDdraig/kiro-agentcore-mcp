# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Unit tests for data quality steering validation.

Tests the pure function validate_sighting_input from
services/agent/steering/data_quality.py with coordinates inside/outside
Australian bounds, valid/invalid conservation statuses, and date handling.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

# Ensure project root is on sys.path
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from services.agent.steering.data_quality import validate_sighting_input


# ===================================================================
# Valid inputs
# ===================================================================
class TestValidInputs:
    """Inputs that should pass all validation checks."""

    def test_valid_sighting(self) -> None:
        """A fully valid sighting passes validation."""
        result = validate_sighting_input(
            latitude=-33.87,
            longitude=151.21,
            conservation_status="vulnerable",
            date_str="2024-06-15",
        )
        assert result["valid"] is True
        assert result["errors"] == []

    def test_boundary_latitude_min(self) -> None:
        """Latitude at the minimum Australian bound (-44) is valid."""
        result = validate_sighting_input(
            latitude=-44.0,
            longitude=130.0,
            conservation_status="endangered",
            date_str="2024-01-01",
        )
        assert result["valid"] is True

    def test_boundary_latitude_max(self) -> None:
        """Latitude at the maximum Australian bound (-10) is valid."""
        result = validate_sighting_input(
            latitude=-10.0,
            longitude=130.0,
            conservation_status="endangered",
            date_str="2024-01-01",
        )
        assert result["valid"] is True

    def test_boundary_longitude_min(self) -> None:
        """Longitude at the minimum Australian bound (113) is valid."""
        result = validate_sighting_input(
            latitude=-25.0,
            longitude=113.0,
            conservation_status="least_concern",
            date_str="2024-01-01",
        )
        assert result["valid"] is True

    def test_boundary_longitude_max(self) -> None:
        """Longitude at the maximum Australian bound (154) is valid."""
        result = validate_sighting_input(
            latitude=-25.0,
            longitude=154.0,
            conservation_status="least_concern",
            date_str="2024-01-01",
        )
        assert result["valid"] is True

    def test_today_date_is_valid(self) -> None:
        """Today's date is valid (not in the future)."""
        today_str = date.today().isoformat()
        result = validate_sighting_input(
            latitude=-30.0,
            longitude=140.0,
            conservation_status="near_threatened",
            date_str=today_str,
        )
        assert result["valid"] is True

    def test_past_date_is_valid(self) -> None:
        """A past date is valid."""
        past_str = (date.today() - timedelta(days=30)).isoformat()
        result = validate_sighting_input(
            latitude=-30.0,
            longitude=140.0,
            conservation_status="critically_endangered",
            date_str=past_str,
        )
        assert result["valid"] is True


# ===================================================================
# All valid conservation statuses
# ===================================================================
class TestConservationStatuses:
    """Each valid IUCN status is accepted."""

    @pytest.mark.parametrize(
        "status",
        [
            "critically_endangered",
            "endangered",
            "vulnerable",
            "near_threatened",
            "least_concern",
        ],
    )
    def test_valid_status_accepted(self, status: str) -> None:
        """Each valid conservation status passes validation."""
        result = validate_sighting_input(
            latitude=-25.0,
            longitude=135.0,
            conservation_status=status,
            date_str="2024-06-01",
        )
        assert result["valid"] is True


# ===================================================================
# Invalid coordinates
# ===================================================================
class TestInvalidCoordinates:
    """Coordinates outside Australian bounds are rejected."""

    def test_latitude_too_far_south(self) -> None:
        """Latitude below -44 is rejected."""
        result = validate_sighting_input(
            latitude=-45.0,
            longitude=140.0,
            conservation_status="vulnerable",
            date_str="2024-06-01",
        )
        assert result["valid"] is False
        assert any("Latitude" in e for e in result["errors"])

    def test_latitude_too_far_north(self) -> None:
        """Latitude above -10 is rejected."""
        result = validate_sighting_input(
            latitude=-9.0,
            longitude=140.0,
            conservation_status="vulnerable",
            date_str="2024-06-01",
        )
        assert result["valid"] is False
        assert any("Latitude" in e for e in result["errors"])

    def test_longitude_too_far_west(self) -> None:
        """Longitude below 113 is rejected."""
        result = validate_sighting_input(
            latitude=-25.0,
            longitude=112.0,
            conservation_status="vulnerable",
            date_str="2024-06-01",
        )
        assert result["valid"] is False
        assert any("Longitude" in e for e in result["errors"])

    def test_longitude_too_far_east(self) -> None:
        """Longitude above 154 is rejected."""
        result = validate_sighting_input(
            latitude=-25.0,
            longitude=155.0,
            conservation_status="vulnerable",
            date_str="2024-06-01",
        )
        assert result["valid"] is False
        assert any("Longitude" in e for e in result["errors"])


# ===================================================================
# Invalid conservation status
# ===================================================================
class TestInvalidConservationStatus:
    """Invalid conservation statuses are rejected."""

    def test_unknown_status(self) -> None:
        """An unrecognised status string is rejected."""
        result = validate_sighting_input(
            latitude=-25.0,
            longitude=135.0,
            conservation_status="extinct",
            date_str="2024-06-01",
        )
        assert result["valid"] is False
        assert any("conservation status" in e.lower() for e in result["errors"])

    def test_empty_status(self) -> None:
        """An empty status string is rejected."""
        result = validate_sighting_input(
            latitude=-25.0,
            longitude=135.0,
            conservation_status="",
            date_str="2024-06-01",
        )
        assert result["valid"] is False


# ===================================================================
# Invalid dates
# ===================================================================
class TestInvalidDates:
    """Future dates and malformed date strings are rejected."""

    def test_future_date_rejected(self) -> None:
        """A date in the future is rejected."""
        future_str = (date.today() + timedelta(days=10)).isoformat()
        result = validate_sighting_input(
            latitude=-25.0,
            longitude=135.0,
            conservation_status="vulnerable",
            date_str=future_str,
        )
        assert result["valid"] is False
        assert any("future" in e.lower() for e in result["errors"])

    def test_invalid_date_format(self) -> None:
        """A malformed date string is rejected."""
        result = validate_sighting_input(
            latitude=-25.0,
            longitude=135.0,
            conservation_status="vulnerable",
            date_str="15/06/2024",
        )
        assert result["valid"] is False
        assert any("date format" in e.lower() or "invalid date" in e.lower() for e in result["errors"])

    def test_nonsense_date_string(self) -> None:
        """A completely invalid date string is rejected."""
        result = validate_sighting_input(
            latitude=-25.0,
            longitude=135.0,
            conservation_status="vulnerable",
            date_str="not-a-date",
        )
        assert result["valid"] is False


# ===================================================================
# Multiple errors
# ===================================================================
class TestMultipleErrors:
    """Multiple validation failures are reported together."""

    def test_multiple_errors_returned(self) -> None:
        """Bad coords, bad status, and bad date all produce errors."""
        future_str = (date.today() + timedelta(days=5)).isoformat()
        result = validate_sighting_input(
            latitude=0.0,
            longitude=0.0,
            conservation_status="invalid",
            date_str=future_str,
        )
        assert result["valid"] is False
        assert len(result["errors"]) >= 3
