# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Property-based tests for Strands steering handlers.

Uses hypothesis to verify:
- Property 20: Data quality steering validates sighting inputs (biconditional).
- Property 21: Safety steering includes emergency info for elevated fire danger.

Tests services/agent/steering/data_quality.py and services/agent/steering/safety.py.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

# Ensure project root is on sys.path
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from services.agent.steering.data_quality import (
    LATITUDE_MAX,
    LATITUDE_MIN,
    LONGITUDE_MAX,
    LONGITUDE_MIN,
    VALID_CONSERVATION_STATUSES,
    validate_sighting_input,
)
from services.agent.steering.safety import (
    ELEVATED_DANGER_LEVELS,
    EMERGENCY_CONTACT,
    SAFETY_ACTIONS,
    get_safety_guidance,
)

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------
_valid_lat_st = st.floats(min_value=LATITUDE_MIN, max_value=LATITUDE_MAX, allow_nan=False, allow_infinity=False)
_valid_lng_st = st.floats(min_value=LONGITUDE_MIN, max_value=LONGITUDE_MAX, allow_nan=False, allow_infinity=False)
_valid_status_st = st.sampled_from(sorted(VALID_CONSERVATION_STATUSES))
_valid_date_st = st.dates(
    min_value=date(2000, 1, 1),
    max_value=date.today(),
).map(lambda d: d.isoformat())

# Invalid strategies
_invalid_lat_st = st.one_of(
    st.floats(min_value=-90.0, max_value=LATITUDE_MIN - 0.01, allow_nan=False, allow_infinity=False),
    st.floats(min_value=LATITUDE_MAX + 0.01, max_value=90.0, allow_nan=False, allow_infinity=False),
)
_invalid_lng_st = st.one_of(
    st.floats(min_value=-180.0, max_value=LONGITUDE_MIN - 0.01, allow_nan=False, allow_infinity=False),
    st.floats(min_value=LONGITUDE_MAX + 0.01, max_value=180.0, allow_nan=False, allow_infinity=False),
)
_invalid_status_st = st.text(min_size=1, max_size=30).filter(lambda s: s not in VALID_CONSERVATION_STATUSES)
_future_date_st = st.integers(min_value=1, max_value=3650).map(
    lambda days: (date.today() + timedelta(days=days)).isoformat()
)

# Danger level strategies
_elevated_danger_st = st.sampled_from(sorted(ELEVATED_DANGER_LEVELS))
_non_elevated_danger_st = st.sampled_from(["low", "moderate"])


# ===================================================================
# Property 20: Data Quality Steering Validates Sighting Inputs
# ===================================================================
class TestProperty20DataQualitySteeringValidatesSightingInputs:
    """Feature: aws-agentcore-mcp-infrastructure, Property 20: Data quality steering validates sighting inputs."""

    @settings(max_examples=100, database=None)
    @given(
        lat=_valid_lat_st,
        lng=_valid_lng_st,
        status=_valid_status_st,
        date_str=_valid_date_st,
    )
    def test_all_valid_fields_accepted(
        self, lat: float, lng: float, status: str, date_str: str
    ) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 20: Data quality steering validates sighting inputs.

        For any sighting with all fields within valid ranges, the validator
        SHALL accept the input (valid=True, errors=[]).

        **Validates: Requirements 17.2, 17.3, 17.4, 17.5**
        """
        result = validate_sighting_input(lat, lng, status, date_str)
        assert result["valid"] is True, f"Expected valid=True for valid inputs, got errors: {result['errors']}"
        assert result["errors"] == [], f"Expected no errors for valid inputs, got: {result['errors']}"

    @settings(max_examples=100, database=None)
    @given(
        lat=_invalid_lat_st,
        lng=_valid_lng_st,
        status=_valid_status_st,
        date_str=_valid_date_st,
    )
    def test_invalid_latitude_rejected(
        self, lat: float, lng: float, status: str, date_str: str
    ) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 20: Data quality steering validates sighting inputs.

        For any sighting with latitude outside [-44, -10], the validator
        SHALL reject the input and report a latitude error.

        **Validates: Requirements 17.2, 17.3, 17.4, 17.5**
        """
        result = validate_sighting_input(lat, lng, status, date_str)
        assert result["valid"] is False, f"Expected valid=False for invalid latitude {lat}"
        assert len(result["errors"]) > 0, "Expected at least one error"
        assert any("Latitude" in e or "latitude" in e for e in result["errors"]), (
            f"Expected latitude error in: {result['errors']}"
        )

    @settings(max_examples=100, database=None)
    @given(
        lat=_valid_lat_st,
        lng=_invalid_lng_st,
        status=_valid_status_st,
        date_str=_valid_date_st,
    )
    def test_invalid_longitude_rejected(
        self, lat: float, lng: float, status: str, date_str: str
    ) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 20: Data quality steering validates sighting inputs.

        For any sighting with longitude outside [113, 154], the validator
        SHALL reject the input and report a longitude error.

        **Validates: Requirements 17.2, 17.3, 17.4, 17.5**
        """
        result = validate_sighting_input(lat, lng, status, date_str)
        assert result["valid"] is False, f"Expected valid=False for invalid longitude {lng}"
        assert len(result["errors"]) > 0, "Expected at least one error"
        assert any("Longitude" in e or "longitude" in e for e in result["errors"]), (
            f"Expected longitude error in: {result['errors']}"
        )

    @settings(max_examples=100, database=None)
    @given(
        lat=_valid_lat_st,
        lng=_valid_lng_st,
        status=_invalid_status_st,
        date_str=_valid_date_st,
    )
    def test_invalid_conservation_status_rejected(
        self, lat: float, lng: float, status: str, date_str: str
    ) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 20: Data quality steering validates sighting inputs.

        For any sighting with an invalid conservation status, the validator
        SHALL reject the input and report a status error.

        **Validates: Requirements 17.2, 17.3, 17.4, 17.5**
        """
        result = validate_sighting_input(lat, lng, status, date_str)
        assert result["valid"] is False, f"Expected valid=False for invalid status '{status}'"
        assert len(result["errors"]) > 0, "Expected at least one error"
        assert any("conservation status" in e.lower() or "status" in e.lower() for e in result["errors"]), (
            f"Expected status error in: {result['errors']}"
        )

    @settings(max_examples=100, database=None)
    @given(
        lat=_valid_lat_st,
        lng=_valid_lng_st,
        status=_valid_status_st,
        date_str=_future_date_st,
    )
    def test_future_date_rejected(
        self, lat: float, lng: float, status: str, date_str: str
    ) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 20: Data quality steering validates sighting inputs.

        For any sighting with a future date, the validator SHALL reject the
        input and report a date error.

        **Validates: Requirements 17.2, 17.3, 17.4, 17.5**
        """
        result = validate_sighting_input(lat, lng, status, date_str)
        assert result["valid"] is False, f"Expected valid=False for future date '{date_str}'"
        assert len(result["errors"]) > 0, "Expected at least one error"
        assert any("future" in e.lower() for e in result["errors"]), (
            f"Expected future-date error in: {result['errors']}"
        )

    @settings(max_examples=100, database=None)
    @given(
        lat=st.floats(min_value=-90.0, max_value=90.0, allow_nan=False, allow_infinity=False),
        lng=st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False),
        status=st.one_of(_valid_status_st, _invalid_status_st),
        use_future=st.booleans(),
    )
    def test_biconditional_valid_iff_all_fields_in_range(
        self, lat: float, lng: float, status: str, use_future: bool
    ) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 20: Data quality steering validates sighting inputs.

        For any generated lat/lng/status/date combination, the validator accepts
        if and only if ALL fields are within valid ranges.

        **Validates: Requirements 17.2, 17.3, 17.4, 17.5**
        """
        if use_future:
            date_str = (date.today() + timedelta(days=5)).isoformat()
        else:
            date_str = (date.today() - timedelta(days=30)).isoformat()

        lat_ok = LATITUDE_MIN <= lat <= LATITUDE_MAX
        lng_ok = LONGITUDE_MIN <= lng <= LONGITUDE_MAX
        status_ok = status in VALID_CONSERVATION_STATUSES
        date_ok = not use_future

        all_valid = lat_ok and lng_ok and status_ok and date_ok

        result = validate_sighting_input(lat, lng, status, date_str)

        if all_valid:
            assert result["valid"] is True, (
                f"Expected valid=True when all fields valid (lat={lat}, lng={lng}, "
                f"status={status}, date={date_str}), got errors: {result['errors']}"
            )
            assert result["errors"] == []
        else:
            assert result["valid"] is False, (
                f"Expected valid=False when some field invalid (lat_ok={lat_ok}, "
                f"lng_ok={lng_ok}, status_ok={status_ok}, date_ok={date_ok})"
            )
            assert len(result["errors"]) > 0, "Expected at least one error for invalid input"


# ===================================================================
# Property 21: Safety Steering Includes Emergency Info for Elevated Fire Danger
# ===================================================================
class TestProperty21SafetySteeringIncludesEmergencyInfo:
    """Feature: aws-agentcore-mcp-infrastructure, Property 21: Safety steering includes emergency info for elevated fire danger."""

    @settings(max_examples=100, database=None)
    @given(danger_level=_elevated_danger_st)
    def test_elevated_danger_includes_emergency_contact(self, danger_level: str) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 21: Safety steering includes emergency info for elevated fire danger.

        For any elevated fire danger level (high, very_high, extreme), the
        safety guidance SHALL include the emergency contact number "000".

        **Validates: Requirements 17.7**
        """
        result = get_safety_guidance(danger_level)
        assert result["requires_warning"] is True, (
            f"Expected requires_warning=True for danger level '{danger_level}'"
        )
        assert result["emergency_contact"] == EMERGENCY_CONTACT, (
            f"Expected emergency_contact='{EMERGENCY_CONTACT}', got '{result['emergency_contact']}'"
        )

    @settings(max_examples=100, database=None)
    @given(danger_level=_elevated_danger_st)
    def test_elevated_danger_has_safety_actions(self, danger_level: str) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 21: Safety steering includes emergency info for elevated fire danger.

        For any elevated fire danger level, the safety guidance SHALL include
        non-empty danger-level-appropriate safety action recommendations.

        **Validates: Requirements 17.7**
        """
        result = get_safety_guidance(danger_level)
        actions = result["recommended_actions"]
        assert isinstance(actions, list), "recommended_actions must be a list"
        assert len(actions) > 0, f"Expected non-empty actions for danger level '{danger_level}'"
        assert actions == SAFETY_ACTIONS[danger_level], (
            f"Actions for '{danger_level}' do not match SAFETY_ACTIONS constant"
        )

    @settings(max_examples=100, database=None)
    @given(danger_level=_elevated_danger_st)
    def test_elevated_danger_response_contains_000(self, danger_level: str) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 21: Safety steering includes emergency info for elevated fire danger.

        For any elevated fire danger level, the steered response contains "000".

        **Validates: Requirements 17.7**
        """
        result = get_safety_guidance(danger_level)
        assert "000" in str(result["emergency_contact"]), (
            f"Expected '000' in emergency_contact for danger level '{danger_level}'"
        )

    @settings(max_examples=100, database=None)
    @given(danger_level=_non_elevated_danger_st)
    def test_non_elevated_danger_no_warning(self, danger_level: str) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 21: Safety steering includes emergency info for elevated fire danger.

        For any non-elevated fire danger level (low, moderate), the safety
        guidance SHALL NOT require a warning and SHALL have empty emergency contact.

        **Validates: Requirements 17.7**
        """
        result = get_safety_guidance(danger_level)
        assert result["requires_warning"] is False, (
            f"Expected requires_warning=False for danger level '{danger_level}'"
        )
        assert result["emergency_contact"] == "", (
            f"Expected empty emergency_contact for danger level '{danger_level}'"
        )
        assert result["recommended_actions"] == [], (
            f"Expected empty actions for danger level '{danger_level}'"
        )
