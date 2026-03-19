# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Data quality steering handler for Australian wildlife sighting records.

Validates coordinate bounds, IUCN conservation status, and sighting dates
before create_sighting tool calls are executed.
"""

from __future__ import annotations

from datetime import date, datetime

from strands.vended_plugins.steering import LLMSteeringHandler

# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------
LATITUDE_MIN = -44.0
LATITUDE_MAX = -10.0
LONGITUDE_MIN = 113.0
LONGITUDE_MAX = 154.0

VALID_CONSERVATION_STATUSES = frozenset(
    {
        "critically_endangered",
        "endangered",
        "vulnerable",
        "near_threatened",
        "least_concern",
    }
)

# ---------------------------------------------------------------------------
# LLM steering prompt
# ---------------------------------------------------------------------------
DATA_QUALITY_PROMPT = """You are a data quality validator for Australian wildlife sighting records.

When the agent is about to call create_sighting, validate:
1. Coordinates are within Australia (latitude: -44 to -10, longitude: 113 to 154)
2. conservation_status is one of: critically_endangered, endangered, vulnerable, near_threatened, least_concern
3. The sighting date is not in the future

If any validation fails, return a Guide action that:
- Cancels the tool call
- Tells the agent exactly what needs correction
- Suggests the correct format or valid values

If all validations pass, allow the tool call to proceed."""

data_quality_handler = LLMSteeringHandler(system_prompt=DATA_QUALITY_PROMPT)


# ---------------------------------------------------------------------------
# Pure validation function (used by unit tests and property tests)
# ---------------------------------------------------------------------------
def validate_sighting_input(
    latitude: float,
    longitude: float,
    conservation_status: str,
    date_str: str,
) -> dict[str, object]:
    """Validate wildlife sighting input fields.

    Args:
        latitude: Decimal degrees latitude of the sighting.
        longitude: Decimal degrees longitude of the sighting.
        conservation_status: IUCN conservation status string.
        date_str: ISO 8601 date string (YYYY-MM-DD) of the sighting.

    Returns:
        A dict with ``valid`` (bool) and ``errors`` (list of str).
    """
    errors: list[str] = []

    if not (LATITUDE_MIN <= latitude <= LATITUDE_MAX):
        errors.append(
            f"Latitude {latitude} is outside Australian bounds ({LATITUDE_MIN} to {LATITUDE_MAX})"
        )

    if not (LONGITUDE_MIN <= longitude <= LONGITUDE_MAX):
        errors.append(
            f"Longitude {longitude} is outside Australian bounds ({LONGITUDE_MIN} to {LONGITUDE_MAX})"
        )

    if conservation_status not in VALID_CONSERVATION_STATUSES:
        errors.append(
            f"Invalid conservation status '{conservation_status}'. "
            f"Must be one of: {', '.join(sorted(VALID_CONSERVATION_STATUSES))}"
        )

    try:
        sighting_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if sighting_date > date.today():
            errors.append(f"Sighting date {date_str} is in the future")
    except ValueError:
        errors.append(f"Invalid date format '{date_str}'. Expected YYYY-MM-DD")

    return {"valid": len(errors) == 0, "errors": errors}
