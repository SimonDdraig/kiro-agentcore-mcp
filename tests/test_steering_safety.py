# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Unit tests for safety steering guidance.

Tests the pure function get_safety_guidance from
services/agent/steering/safety.py for each fire danger level,
verifying emergency info and recommended actions.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from services.agent.steering.safety import SAFETY_ACTIONS, get_safety_guidance


# ===================================================================
# Low and moderate — no warning required
# ===================================================================
class TestLowDangerLevel:
    """Low fire danger requires no warning."""

    def test_requires_warning_false(self) -> None:
        """Low danger does not require a warning."""
        result = get_safety_guidance("low")
        assert result["requires_warning"] is False

    def test_emergency_contact_empty(self) -> None:
        """Low danger has no emergency contact."""
        result = get_safety_guidance("low")
        assert result["emergency_contact"] == ""

    def test_no_recommended_actions(self) -> None:
        """Low danger has no recommended actions."""
        result = get_safety_guidance("low")
        assert result["recommended_actions"] == []


class TestModerateDangerLevel:
    """Moderate fire danger requires no warning."""

    def test_requires_warning_false(self) -> None:
        """Moderate danger does not require a warning."""
        result = get_safety_guidance("moderate")
        assert result["requires_warning"] is False

    def test_emergency_contact_empty(self) -> None:
        """Moderate danger has no emergency contact."""
        result = get_safety_guidance("moderate")
        assert result["emergency_contact"] == ""

    def test_no_recommended_actions(self) -> None:
        """Moderate danger has no recommended actions."""
        result = get_safety_guidance("moderate")
        assert result["recommended_actions"] == []


# ===================================================================
# High — warning required
# ===================================================================
class TestHighDangerLevel:
    """High fire danger requires a warning with emergency info."""

    def test_requires_warning_true(self) -> None:
        """High danger requires a warning."""
        result = get_safety_guidance("high")
        assert result["requires_warning"] is True

    def test_emergency_contact_000(self) -> None:
        """High danger includes emergency contact 000."""
        result = get_safety_guidance("high")
        assert result["emergency_contact"] == "000"

    def test_has_recommended_actions(self) -> None:
        """High danger has non-empty recommended actions."""
        result = get_safety_guidance("high")
        assert len(result["recommended_actions"]) > 0

    def test_actions_match_defined_actions(self) -> None:
        """High danger actions match the SAFETY_ACTIONS constant."""
        result = get_safety_guidance("high")
        assert result["recommended_actions"] == SAFETY_ACTIONS["high"]


# ===================================================================
# Very high — warning required
# ===================================================================
class TestVeryHighDangerLevel:
    """Very high fire danger requires a warning with emergency info."""

    def test_requires_warning_true(self) -> None:
        """Very high danger requires a warning."""
        result = get_safety_guidance("very_high")
        assert result["requires_warning"] is True

    def test_emergency_contact_000(self) -> None:
        """Very high danger includes emergency contact 000."""
        result = get_safety_guidance("very_high")
        assert result["emergency_contact"] == "000"

    def test_has_recommended_actions(self) -> None:
        """Very high danger has non-empty recommended actions."""
        result = get_safety_guidance("very_high")
        assert len(result["recommended_actions"]) > 0

    def test_actions_match_defined_actions(self) -> None:
        """Very high danger actions match the SAFETY_ACTIONS constant."""
        result = get_safety_guidance("very_high")
        assert result["recommended_actions"] == SAFETY_ACTIONS["very_high"]


# ===================================================================
# Extreme — warning required
# ===================================================================
class TestExtremeDangerLevel:
    """Extreme fire danger requires a warning with emergency info."""

    def test_requires_warning_true(self) -> None:
        """Extreme danger requires a warning."""
        result = get_safety_guidance("extreme")
        assert result["requires_warning"] is True

    def test_emergency_contact_000(self) -> None:
        """Extreme danger includes emergency contact 000."""
        result = get_safety_guidance("extreme")
        assert result["emergency_contact"] == "000"

    def test_has_recommended_actions(self) -> None:
        """Extreme danger has non-empty recommended actions."""
        result = get_safety_guidance("extreme")
        assert len(result["recommended_actions"]) > 0

    def test_actions_match_defined_actions(self) -> None:
        """Extreme danger actions match the SAFETY_ACTIONS constant."""
        result = get_safety_guidance("extreme")
        assert result["recommended_actions"] == SAFETY_ACTIONS["extreme"]

    def test_extreme_includes_evacuate(self) -> None:
        """Extreme danger actions include evacuation."""
        result = get_safety_guidance("extreme")
        actions_text = " ".join(result["recommended_actions"]).lower()
        assert "evacuate" in actions_text


# ===================================================================
# Specific action content per level
# ===================================================================
class TestSpecificActions:
    """Verify specific expected actions per danger level."""

    def test_high_includes_vigilance(self) -> None:
        """High danger includes increased vigilance."""
        result = get_safety_guidance("high")
        actions_text = " ".join(result["recommended_actions"]).lower()
        assert "vigilance" in actions_text

    def test_very_high_includes_restrict(self) -> None:
        """Very high danger includes restricting field activities."""
        result = get_safety_guidance("very_high")
        actions_text = " ".join(result["recommended_actions"]).lower()
        assert "restrict" in actions_text

    def test_extreme_includes_cease_operations(self) -> None:
        """Extreme danger includes ceasing non-emergency operations."""
        result = get_safety_guidance("extreme")
        actions_text = " ".join(result["recommended_actions"]).lower()
        assert "cease" in actions_text
