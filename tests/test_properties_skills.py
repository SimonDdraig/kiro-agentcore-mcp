# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Property-based tests for Strands Agent skill definitions.

Uses hypothesis to verify that each SKILL.md file contains complete
instructions with valid YAML frontmatter (name, description, allowed-tools)
and non-empty markdown body content.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

# Ensure project root is on sys.path so modules are importable
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"

EXPECTED_SKILLS = {
    "wildlife-tracking": {
        "description_keywords": ["wildlife", "sighting"],
        "allowed_tools": ["create_sighting", "query_by_species", "query_by_location", "query_by_status"],
    },
    "fire-danger-assessment": {
        "description_keywords": ["fire", "danger"],
        "allowed_tools": ["assess_fire_danger", "get_current_weather", "get_forecast"],
    },
    "conservation-research": {
        "description_keywords": ["conservation", "document"],
        "allowed_tools": ["list_documents", "get_document", "search_documents"],
    },
    "web-research": {
        "description_keywords": ["web", "government"],
        "allowed_tools": ["fetch"],
    },
}

_skill_names_st = st.sampled_from(list(EXPECTED_SKILLS.keys()))


def _read_skill(skill_name: str) -> str:
    """Read the raw SKILL.md content for a given skill."""
    skill_path = _SKILLS_ROOT / skill_name / "SKILL.md"
    return skill_path.read_text(encoding="utf-8")


def _parse_frontmatter(content: str) -> dict:
    """Extract and parse YAML frontmatter from SKILL.md content."""
    parts = content.split("---", 2)
    assert len(parts) >= 3, "SKILL.md missing YAML frontmatter delimiters"
    frontmatter: dict = yaml.safe_load(parts[1])
    return frontmatter


def _extract_body(content: str) -> str:
    """Extract the markdown body (after frontmatter) from SKILL.md content."""
    parts = content.split("---", 2)
    assert len(parts) >= 3, "SKILL.md missing YAML frontmatter delimiters"
    return parts[2]


# ===================================================================
# Property 19: Skill Activation Returns Full Instructions
# ===================================================================
class TestProperty19SkillActivationReturnsFullInstructions:
    """Feature: aws-agentcore-mcp-infrastructure, Property 19: Skill activation returns full instructions."""

    @settings(max_examples=100, database=None)
    @given(skill_name=_skill_names_st)
    def test_skill_md_contains_name_in_frontmatter(self, skill_name: str) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 19: Skill activation returns full instructions.

        For any valid skill, the SKILL.md frontmatter contains a 'name' field
        matching the skill directory name.

        **Validates: Requirements 16.2, 16.4**
        """
        content = _read_skill(skill_name)
        fm = _parse_frontmatter(content)

        assert "name" in fm, f"Frontmatter missing 'name' for skill {skill_name}"
        assert fm["name"] == skill_name, (
            f"Frontmatter name '{fm['name']}' does not match directory name '{skill_name}'"
        )

    @settings(max_examples=100, database=None)
    @given(skill_name=_skill_names_st)
    def test_skill_md_contains_description_in_frontmatter(self, skill_name: str) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 19: Skill activation returns full instructions.

        For any valid skill, the SKILL.md frontmatter contains a non-empty
        'description' field.

        **Validates: Requirements 16.2, 16.4**
        """
        content = _read_skill(skill_name)
        fm = _parse_frontmatter(content)

        assert "description" in fm, f"Frontmatter missing 'description' for skill {skill_name}"
        assert isinstance(fm["description"], str), "Description must be a string"
        assert len(fm["description"].strip()) > 0, "Description must not be empty"

    @settings(max_examples=100, database=None)
    @given(skill_name=_skill_names_st)
    def test_skill_md_contains_allowed_tools_in_frontmatter(self, skill_name: str) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 19: Skill activation returns full instructions.

        For any valid skill, the SKILL.md frontmatter contains an 'allowed-tools'
        list matching the expected tools for that skill.

        **Validates: Requirements 16.2, 16.4**
        """
        content = _read_skill(skill_name)
        fm = _parse_frontmatter(content)

        assert "allowed-tools" in fm, f"Frontmatter missing 'allowed-tools' for skill {skill_name}"
        assert isinstance(fm["allowed-tools"], list), "allowed-tools must be a list"
        assert len(fm["allowed-tools"]) > 0, "allowed-tools must not be empty"

        expected_tools = EXPECTED_SKILLS[skill_name]["allowed_tools"]
        assert set(fm["allowed-tools"]) == set(expected_tools), (
            f"Expected tools {expected_tools}, got {fm['allowed-tools']}"
        )

    @settings(max_examples=100, database=None)
    @given(skill_name=_skill_names_st)
    def test_skill_md_body_is_non_empty(self, skill_name: str) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 19: Skill activation returns full instructions.

        For any valid skill, the markdown body after the YAML frontmatter is
        non-empty, confirming complete instructions are present.

        **Validates: Requirements 16.2, 16.4**
        """
        content = _read_skill(skill_name)
        body = _extract_body(content)

        assert len(body.strip()) > 0, f"SKILL.md body is empty for skill {skill_name}"

    @settings(max_examples=100, database=None)
    @given(skill_name=_skill_names_st)
    def test_skill_content_contains_frontmatter_name(self, skill_name: str) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 19: Skill activation returns full instructions.

        For any valid skill, the complete SKILL.md content contains the skill's
        name as defined in the YAML frontmatter.

        **Validates: Requirements 16.2, 16.4**
        """
        content = _read_skill(skill_name)
        fm = _parse_frontmatter(content)

        assert fm["name"] in content, (
            f"Skill name '{fm['name']}' not found in complete SKILL.md content"
        )

    @settings(max_examples=100, database=None)
    @given(skill_name=_skill_names_st)
    def test_skill_content_contains_frontmatter_description(self, skill_name: str) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 19: Skill activation returns full instructions.

        For any valid skill, the complete SKILL.md content contains the skill's
        description as defined in the YAML frontmatter.

        **Validates: Requirements 16.2, 16.4**
        """
        content = _read_skill(skill_name)
        fm = _parse_frontmatter(content)

        assert fm["description"] in content, (
            f"Skill description not found in complete SKILL.md content"
        )

    @settings(max_examples=100, database=None)
    @given(skill_name=_skill_names_st)
    def test_skill_content_contains_all_allowed_tools(self, skill_name: str) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 19: Skill activation returns full instructions.

        For any valid skill, the complete SKILL.md content references all
        allowed-tools defined in the YAML frontmatter.

        **Validates: Requirements 16.2, 16.4**
        """
        content = _read_skill(skill_name)
        fm = _parse_frontmatter(content)

        for tool in fm["allowed-tools"]:
            assert tool in content, (
                f"Tool '{tool}' from allowed-tools not found in SKILL.md content for {skill_name}"
            )
