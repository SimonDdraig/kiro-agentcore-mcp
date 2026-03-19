# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Unit tests for the Weather & Climate MCP server.

Tests services/mcp_servers/weather/server.py with mocked HTTP responses.
Covers get_current_weather, get_forecast, assess_fire_danger,
calculate_ffdi, ffdi_to_danger_level, and API unavailable error handling.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

# Ensure project root is on sys.path so services/ is importable
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from services.mcp_servers.weather.server import (
    assess_fire_danger,
    calculate_ffdi,
    ffdi_to_danger_level,
    get_current_weather,
    get_forecast,
)

# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------
_PATCH_TARGET = "services.mcp_servers.weather.server.requests.get"


def _mock_response(json_data: dict[str, Any]) -> MagicMock:
    """Return a MagicMock standing in for a requests.Response."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = json_data
    mock_resp.raise_for_status.return_value = None
    return mock_resp


def _current_weather_api_response() -> dict[str, Any]:
    """Return a realistic Open-Meteo current weather API response."""
    return {
        "current": {
            "temperature_2m": 28.5,
            "relative_humidity_2m": 45,
            "wind_speed_10m": 15.3,
            "precipitation": 0.0,
            "weather_code": 1,
        },
        "current_units": {
            "temperature_2m": "°C",
            "relative_humidity_2m": "%",
            "wind_speed_10m": "km/h",
            "precipitation": "mm",
        },
    }


def _forecast_api_response(days: int = 3) -> dict[str, Any]:
    """Return a realistic Open-Meteo forecast API response."""
    dates = [f"2025-07-{10 + i:02d}" for i in range(days)]
    return {
        "daily": {
            "time": dates,
            "temperature_2m_max": [30.0 + i for i in range(days)],
            "temperature_2m_min": [18.0 + i for i in range(days)],
            "precipitation_sum": [0.0] * days,
            "wind_speed_10m_max": [20.0] * days,
        },
        "daily_units": {
            "temperature_2m_max": "°C",
            "precipitation_sum": "mm",
            "wind_speed_10m_max": "km/h",
        },
    }


# ===================================================================
# get_current_weather
# ===================================================================
class TestGetCurrentWeather:
    """Tests for the get_current_weather tool."""

    def test_successful_response(self) -> None:
        """Successful API call returns all expected weather fields."""
        with patch(_PATCH_TARGET, return_value=_mock_response(_current_weather_api_response())):
            result = get_current_weather(lat=-33.87, lng=151.21)

        assert result["latitude"] == -33.87
        assert result["longitude"] == 151.21
        assert result["temperature"] == 28.5
        assert result["humidity"] == 45
        assert result["wind_speed"] == 15.3
        assert result["precipitation"] == 0.0
        assert result["weather_code"] == 1
        assert result["temperature_unit"] == "°C"
        assert result["wind_speed_unit"] == "km/h"

    def test_api_unavailable(self) -> None:
        """API unavailable returns structured service_unavailable error."""
        with patch(_PATCH_TARGET, side_effect=requests.RequestException("Connection error")):
            result = get_current_weather(lat=-33.87, lng=151.21)

        assert result["error"] == "service_unavailable"
        assert "message" in result


# ===================================================================
# get_forecast
# ===================================================================
class TestGetForecast:
    """Tests for the get_forecast tool."""

    def test_successful_response(self) -> None:
        """Successful API call returns daily forecast array with correct day count."""
        with patch(_PATCH_TARGET, return_value=_mock_response(_forecast_api_response(days=3))):
            result = get_forecast(lat=-33.87, lng=151.21, days=3)

        assert result["latitude"] == -33.87
        assert result["longitude"] == 151.21
        assert result["forecast_days"] == 3
        assert len(result["daily"]) == 3
        day = result["daily"][0]
        assert "date" in day
        assert "temperature_max" in day
        assert "temperature_min" in day
        assert "precipitation" in day
        assert "wind_speed_max" in day

    def test_days_clamped_to_valid_range(self) -> None:
        """Days parameter is clamped to 1-16 range."""
        # days=0 should be clamped to 1
        with patch(_PATCH_TARGET, return_value=_mock_response(_forecast_api_response(days=1))):
            result = get_forecast(lat=-33.87, lng=151.21, days=0)
        assert result["forecast_days"] == 1

        # days=20 should be clamped to 16
        with patch(_PATCH_TARGET, return_value=_mock_response(_forecast_api_response(days=16))):
            result = get_forecast(lat=-33.87, lng=151.21, days=20)
        assert result["forecast_days"] == 16

    def test_api_unavailable(self) -> None:
        """API unavailable returns structured service_unavailable error."""
        with patch(_PATCH_TARGET, side_effect=requests.RequestException("Timeout")):
            result = get_forecast(lat=-33.87, lng=151.21, days=7)

        assert result["error"] == "service_unavailable"
        assert "message" in result


# ===================================================================
# assess_fire_danger
# ===================================================================
class TestAssessFireDanger:
    """Tests for the assess_fire_danger tool."""

    def test_successful_response(self) -> None:
        """Successful API call returns fire_danger_level and ffdi."""
        api_data = {
            "current": {
                "temperature_2m": 35.0,
                "relative_humidity_2m": 20,
                "wind_speed_10m": 30.0,
            },
        }
        with patch(_PATCH_TARGET, return_value=_mock_response(api_data)):
            result = assess_fire_danger(lat=-33.87, lng=151.21)

        assert result["latitude"] == -33.87
        assert result["longitude"] == 151.21
        assert "fire_danger_level" in result
        assert result["fire_danger_level"] in ("low", "moderate", "high", "very_high", "extreme")
        assert "ffdi" in result
        assert isinstance(result["ffdi"], float)
        assert result["inputs"]["temperature"] == 35.0
        assert result["inputs"]["humidity"] == 20
        assert result["inputs"]["wind_speed"] == 30.0

    def test_api_unavailable(self) -> None:
        """API unavailable returns structured service_unavailable error."""
        with patch(_PATCH_TARGET, side_effect=requests.RequestException("DNS failure")):
            result = assess_fire_danger(lat=-33.87, lng=151.21)

        assert result["error"] == "service_unavailable"
        assert "message" in result

    def test_missing_weather_data(self) -> None:
        """Missing weather data in API response returns structured error."""
        api_data: dict[str, Any] = {"current": {}}
        with patch(_PATCH_TARGET, return_value=_mock_response(api_data)):
            result = assess_fire_danger(lat=-33.87, lng=151.21)

        assert result["error"] == "service_unavailable"


# ===================================================================
# calculate_ffdi (pure function)
# ===================================================================
class TestCalculateFFDI:
    """Tests for the calculate_ffdi pure function."""

    def test_returns_non_negative_float(self) -> None:
        """FFDI is always a non-negative float."""
        result = calculate_ffdi(temperature=25.0, humidity=50.0, wind_speed=10.0)
        assert isinstance(result, float)
        assert result >= 0.0

    def test_monotonicity(self) -> None:
        """Higher temp + lower humidity + higher wind produces higher FFDI."""
        mild = calculate_ffdi(temperature=20.0, humidity=80.0, wind_speed=5.0)
        severe = calculate_ffdi(temperature=40.0, humidity=10.0, wind_speed=50.0)
        assert severe > mild


# ===================================================================
# ffdi_to_danger_level (pure function)
# ===================================================================
class TestFFDIToDangerLevel:
    """Tests for the ffdi_to_danger_level pure function."""

    @pytest.mark.parametrize(
        ("ffdi", "expected_level"),
        [
            (0.0, "low"),
            (11.9, "low"),
            (12.0, "moderate"),
            (24.9, "moderate"),
            (25.0, "high"),
            (49.9, "high"),
            (50.0, "very_high"),
            (74.9, "very_high"),
            (75.0, "extreme"),
            (100.0, "extreme"),
        ],
    )
    def test_boundary_values(self, ffdi: float, expected_level: str) -> None:
        """FFDI maps to correct danger level at boundary values."""
        assert ffdi_to_danger_level(ffdi) == expected_level
