# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Property-based tests for the Weather & Climate MCP server.

Uses hypothesis to verify correctness properties across randomised inputs.
Tests the pure functions calculate_ffdi and ffdi_to_danger_level from
services/mcp_servers/weather/server.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

from hypothesis import assume, given, settings
from hypothesis import strategies as st

# Ensure project root is on sys.path so services/ is importable
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from services.mcp_servers.weather.server import (
    FIRE_DANGER_LEVELS,
    calculate_ffdi,
    ffdi_to_danger_level,
)

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------
_temp_st = st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False)
_humidity_st = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
_wind_st = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)


# ===================================================================
# Property 9: Fire Danger Monotonicity
# ===================================================================
class TestProperty9FireDangerMonotonicity:
    """Feature: aws-agentcore-mcp-infrastructure, Property 9: Fire Danger Monotonicity."""

    @settings(max_examples=100, database=None)
    @given(
        temp_a=_temp_st,
        temp_b=_temp_st,
        humidity_a=_humidity_st,
        humidity_b=_humidity_st,
        wind_a=_wind_st,
        wind_b=_wind_st,
    )
    def test_fire_danger_monotonicity(
        self,
        temp_a: float,
        temp_b: float,
        humidity_a: float,
        humidity_b: float,
        wind_a: float,
        wind_b: float,
    ) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 9: Fire Danger Monotonicity.

        For two weather conditions where condition A has higher temperature,
        lower humidity, and higher wind speed than condition B, the fire danger
        rating for A SHALL be greater than or equal to the rating for B.

        **Validates: Requirements 3.4**
        """
        # Condition A must be strictly more severe than condition B
        assume(temp_a > temp_b)
        assume(humidity_a < humidity_b)
        assume(wind_a > wind_b)

        ffdi_a = calculate_ffdi(temperature=temp_a, humidity=humidity_a, wind_speed=wind_a)
        ffdi_b = calculate_ffdi(temperature=temp_b, humidity=humidity_b, wind_speed=wind_b)

        # FFDI for the more severe condition must be >= the milder one
        assert ffdi_a >= ffdi_b, (
            f"FFDI monotonicity violated: "
            f"condition A (temp={temp_a}, humidity={humidity_a}, wind={wind_a}) → FFDI={ffdi_a}, "
            f"condition B (temp={temp_b}, humidity={humidity_b}, wind={wind_b}) → FFDI={ffdi_b}"
        )

        # Danger level ordinal for A must be >= ordinal for B
        level_a = ffdi_to_danger_level(ffdi_a)
        level_b = ffdi_to_danger_level(ffdi_b)
        ordinal_a = FIRE_DANGER_LEVELS.index(level_a)
        ordinal_b = FIRE_DANGER_LEVELS.index(level_b)

        assert ordinal_a >= ordinal_b, (
            f"Danger level monotonicity violated: "
            f"condition A → {level_a} (ordinal {ordinal_a}), "
            f"condition B → {level_b} (ordinal {ordinal_b})"
        )
