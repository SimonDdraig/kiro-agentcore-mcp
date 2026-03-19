# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Weather & Climate MCP server — Open-Meteo API tools for weather, forecast, and fire danger."""

from __future__ import annotations

import math
from typing import Any

import requests
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# MCP server instance
# ---------------------------------------------------------------------------
mcp = FastMCP("weather-climate")

# ---------------------------------------------------------------------------
# Open-Meteo API configuration
# ---------------------------------------------------------------------------
_OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1"
_REQUEST_TIMEOUT_SECONDS = 10

# ---------------------------------------------------------------------------
# Fire danger rating levels (ordered low → extreme)
# ---------------------------------------------------------------------------
FIRE_DANGER_LEVELS = ("low", "moderate", "high", "very_high", "extreme")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _service_unavailable_error() -> dict[str, Any]:
    """Return a structured error for Open-Meteo API unavailability."""
    return {
        "error": "service_unavailable",
        "message": "The Open-Meteo weather service is currently unavailable. Please try again later.",
    }


def _call_open_meteo(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    """Make a GET request to the Open-Meteo API.

    Args:
        endpoint: API endpoint path (e.g. '/forecast').
        params: Query parameters.

    Returns:
        Parsed JSON response dict.

    Raises:
        requests.RequestException: If the API is unreachable or returns an error.
    """
    url = f"{_OPEN_METEO_BASE_URL}{endpoint}"
    response = requests.get(url, params=params, timeout=_REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    result: dict[str, Any] = response.json()
    return result


# ---------------------------------------------------------------------------
# Fire danger calculation — simplified McArthur Forest Fire Danger Index
# ---------------------------------------------------------------------------


def calculate_ffdi(temperature: float, humidity: float, wind_speed: float) -> float:
    """Calculate a simplified McArthur Forest Fire Danger Index (FFDI).

    Uses the Mark 5 formula approximation:
        FFDI = 2.0 * exp(0.987 * ln(DF) - 0.0345 * RH + 0.0338 * T + 0.0234 * V)

    For simplicity we use a fixed Drought Factor (DF) of 5.0 (moderate drought).

    The formula is monotonic with respect to:
    - Temperature (T): higher T → higher FFDI
    - Humidity (RH): lower RH → higher FFDI (negative coefficient)
    - Wind speed (V): higher V → higher FFDI

    Args:
        temperature: Temperature in degrees Celsius.
        humidity: Relative humidity as a percentage (0-100).
        wind_speed: Wind speed in km/h.

    Returns:
        The FFDI value (non-negative float).
    """
    drought_factor = 5.0
    ln_df = math.log(max(drought_factor, 0.01))

    ffdi = 2.0 * math.exp(0.987 * ln_df - 0.0345 * humidity + 0.0338 * temperature + 0.0234 * wind_speed)
    return max(ffdi, 0.0)


def ffdi_to_danger_level(ffdi: float) -> str:
    """Map an FFDI value to a fire danger rating level.

    Thresholds based on the Australian fire danger rating system:
        - low:       FFDI < 12
        - moderate:  12 ≤ FFDI < 25
        - high:      25 ≤ FFDI < 50
        - very_high: 50 ≤ FFDI < 75
        - extreme:   FFDI ≥ 75

    Args:
        ffdi: The calculated FFDI value.

    Returns:
        One of 'low', 'moderate', 'high', 'very_high', 'extreme'.
    """
    if ffdi < 12:
        return "low"
    if ffdi < 25:
        return "moderate"
    if ffdi < 50:
        return "high"
    if ffdi < 75:
        return "very_high"
    return "extreme"


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def get_current_weather(lat: float, lng: float) -> dict[str, Any]:
    """Get current weather conditions for a location.

    Queries the Open-Meteo API for real-time weather data including
    temperature, humidity, wind speed, precipitation, and weather code.

    Args:
        lat: Latitude of the location.
        lng: Longitude of the location.

    Returns:
        A dict with current weather data or a structured error if the
        service is unavailable.
    """
    params = {
        "latitude": lat,
        "longitude": lng,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation,weather_code",
    }

    try:
        data = _call_open_meteo("/forecast", params)
    except (requests.RequestException, ValueError, KeyError):
        return _service_unavailable_error()

    current = data.get("current", {})
    units = data.get("current_units", {})

    return {
        "latitude": lat,
        "longitude": lng,
        "temperature": current.get("temperature_2m"),
        "temperature_unit": units.get("temperature_2m", "°C"),
        "humidity": current.get("relative_humidity_2m"),
        "humidity_unit": units.get("relative_humidity_2m", "%"),
        "wind_speed": current.get("wind_speed_10m"),
        "wind_speed_unit": units.get("wind_speed_10m", "km/h"),
        "precipitation": current.get("precipitation"),
        "precipitation_unit": units.get("precipitation", "mm"),
        "weather_code": current.get("weather_code"),
    }


@mcp.tool()
def get_forecast(lat: float, lng: float, days: int = 7) -> dict[str, Any]:
    """Get a multi-day weather forecast for a location.

    Queries the Open-Meteo API for daily forecast data including
    temperature min/max, precipitation sum, and maximum wind speed.

    Args:
        lat: Latitude of the location.
        lng: Longitude of the location.
        days: Number of forecast days (1-16). Defaults to 7.

    Returns:
        A dict with daily forecast array or a structured error if the
        service is unavailable.
    """
    days = max(1, min(days, 16))

    params = {
        "latitude": lat,
        "longitude": lng,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
        "forecast_days": days,
    }

    try:
        data = _call_open_meteo("/forecast", params)
    except (requests.RequestException, ValueError, KeyError):
        return _service_unavailable_error()

    daily = data.get("daily", {})
    daily_units = data.get("daily_units", {})

    dates = daily.get("time", [])
    temp_max = daily.get("temperature_2m_max", [])
    temp_min = daily.get("temperature_2m_min", [])
    precip = daily.get("precipitation_sum", [])
    wind_max = daily.get("wind_speed_10m_max", [])

    forecast_days: list[dict[str, Any]] = []
    for i in range(len(dates)):
        forecast_days.append(
            {
                "date": dates[i] if i < len(dates) else None,
                "temperature_max": temp_max[i] if i < len(temp_max) else None,
                "temperature_min": temp_min[i] if i < len(temp_min) else None,
                "precipitation": precip[i] if i < len(precip) else None,
                "wind_speed_max": wind_max[i] if i < len(wind_max) else None,
            }
        )

    return {
        "latitude": lat,
        "longitude": lng,
        "forecast_days": days,
        "units": {
            "temperature": daily_units.get("temperature_2m_max", "°C"),
            "precipitation": daily_units.get("precipitation_sum", "mm"),
            "wind_speed": daily_units.get("wind_speed_10m_max", "km/h"),
        },
        "daily": forecast_days,
    }


@mcp.tool()
def assess_fire_danger(lat: float, lng: float) -> dict[str, Any]:
    """Assess fire danger for a location based on current weather conditions.

    Fetches current temperature, humidity, and wind speed from the
    Open-Meteo API, then calculates a simplified McArthur Forest Fire
    Danger Index (FFDI) to determine the fire danger rating.

    Args:
        lat: Latitude of the location.
        lng: Longitude of the location.

    Returns:
        A dict with fire danger level, FFDI value, and the weather inputs
        used for the calculation, or a structured error if the service is
        unavailable.
    """
    params = {
        "latitude": lat,
        "longitude": lng,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m",
    }

    try:
        data = _call_open_meteo("/forecast", params)
    except (requests.RequestException, ValueError, KeyError):
        return _service_unavailable_error()

    current = data.get("current", {})

    temperature = current.get("temperature_2m")
    humidity = current.get("relative_humidity_2m")
    wind_speed = current.get("wind_speed_10m")

    if temperature is None or humidity is None or wind_speed is None:
        return _service_unavailable_error()

    ffdi = calculate_ffdi(float(temperature), float(humidity), float(wind_speed))
    danger_level = ffdi_to_danger_level(ffdi)

    return {
        "latitude": lat,
        "longitude": lng,
        "fire_danger_level": danger_level,
        "ffdi": round(ffdi, 2),
        "inputs": {
            "temperature": temperature,
            "humidity": humidity,
            "wind_speed": wind_speed,
        },
    }


# ---------------------------------------------------------------------------
# Server entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
