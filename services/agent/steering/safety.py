# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Safety steering handler for Australian park ranger fire danger responses.

Detects elevated fire danger levels and ensures the agent includes
emergency contact information and danger-level-appropriate safety actions.
"""

from __future__ import annotations

from strands.vended_plugins.steering import LLMSteeringHandler

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EMERGENCY_CONTACT = "000"

ELEVATED_DANGER_LEVELS = frozenset({"high", "very_high", "extreme"})

SAFETY_ACTIONS: dict[str, list[str]] = {
    "high": [
        "Increased vigilance during field patrols",
        "Check fire breaks and clear accumulated debris",
        "Ensure communication equipment is charged and operational",
        "Confirm evacuation routes are clear and known to all team members",
    ],
    "very_high": [
        "Restrict field activities to essential operations only",
        "Notify base of your exact location and expected return time",
        "Prepare evacuation routes and identify safe refuge points",
        "Maintain continuous radio contact with base",
        "Postpone non-critical surveys and research activities",
    ],
    "extreme": [
        "Evacuate to designated safe zones immediately",
        "Cease all non-emergency field operations",
        "Contact the local fire authority and report your status",
        "Follow all directives from emergency services",
        "Do not re-enter the field until danger level drops and clearance is given",
    ],
}

# ---------------------------------------------------------------------------
# LLM steering prompt
# ---------------------------------------------------------------------------
SAFETY_PROMPT = """You are a safety advisor for Australian park rangers.

After the agent assesses fire danger or retrieves weather data:
- If fire danger is "high", "very_high", or "extreme", ensure the response includes:
  1. A clear safety warning about the danger level
  2. Emergency contact: Emergency 000
  3. Recommended ranger actions for that danger level:
     - high: Increased vigilance, check fire breaks, ensure communication equipment ready
     - very_high: Restrict field activities to essential only, notify base of location, prepare evacuation routes
     - extreme: Evacuate to safe zones, cease all non-emergency field operations, contact local fire authority
  4. Advice to monitor conditions and check for updates

If fire danger is low or moderate, no additional steering is needed."""

safety_handler = LLMSteeringHandler(system_prompt=SAFETY_PROMPT)


# ---------------------------------------------------------------------------
# Pure guidance function (used by unit tests and property tests)
# ---------------------------------------------------------------------------
def get_safety_guidance(danger_level: str) -> dict[str, object]:
    """Return safety guidance for a given fire danger level.

    Args:
        danger_level: One of low, moderate, high, very_high, extreme.

    Returns:
        A dict with ``requires_warning`` (bool), ``emergency_contact`` (str),
        and ``recommended_actions`` (list of str).
    """
    requires_warning = danger_level in ELEVATED_DANGER_LEVELS
    recommended_actions: list[str] = SAFETY_ACTIONS.get(danger_level, [])

    return {
        "requires_warning": requires_warning,
        "emergency_contact": EMERGENCY_CONTACT if requires_warning else "",
        "recommended_actions": recommended_actions,
    }
