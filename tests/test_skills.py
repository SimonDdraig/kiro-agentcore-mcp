# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Unit tests for Strands Agent skill definitions.

Verifies each SKILL.md parses correctly (valid YAML frontmatter with name,
description, allowed-tools), skill content contains expected domain keywords,
and all four skill directories exist.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"

EXPECTED_SKILLS = [
    "wildlife-tracking",
    "fire-danger-assessment",
    "conservation-research",
    "web-research",
]


def _parse_skill(skill_name: str) -> tuple[dict, str]:
    """Parse a SKILL.md file and return (frontmatter_dict, body_text)."""
    skill_path = _SKILLS_ROOT / skill_name / "SKILL.md"
    content = skill_path.read_text(encoding="utf-8")
    # Split on YAML frontmatter delimiters
    parts = content.split("---", 2)
    assert len(parts) >= 3, f"SKILL.md for {skill_name} missing YAML frontmatter delimiters"
    frontmatter = yaml.safe_load(parts[1])
    body = parts[2]
    return frontmatter, body


# ===================================================================
# Skill directories exist
# ===================================================================
class TestSkillDirectoriesExist:
    """All four skill directories must exist."""

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_skill_directory_exists(self, skill_name: str) -> None:
        """Skill directory exists under skills/."""
        skill_dir = _SKILLS_ROOT / skill_name
        assert skill_dir.is_dir(), f"Skill directory {skill_dir} does not exist"

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_skill_md_exists(self, skill_name: str) -> None:
        """SKILL.md file exists inside each skill directory."""
        skill_md = _SKILLS_ROOT / skill_name / "SKILL.md"
        assert skill_md.is_file(), f"SKILL.md not found at {skill_md}"


# ===================================================================
# YAML frontmatter parsing
# ===================================================================
class TestSkillFrontmatter:
    """Each SKILL.md has valid YAML frontmatter with required fields."""

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_frontmatter_has_name(self, skill_name: str) -> None:
        """Frontmatter contains 'name' field."""
        fm, _ = _parse_skill(skill_name)
        assert "name" in fm, f"{skill_name} frontmatter missing 'name'"
        assert isinstance(fm["name"], str)

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_frontmatter_has_description(self, skill_name: str) -> None:
        """Frontmatter contains 'description' field."""
        fm, _ = _parse_skill(skill_name)
        assert "description" in fm, f"{skill_name} frontmatter missing 'description'"
        assert isinstance(fm["description"], str)

    @pytest.mark.parametrize("skill_name", EXPECTED_SKILLS)
    def test_frontmatter_has_allowed_tools(self, skill_name: str) -> None:
        """Frontmatter contains 'allowed-tools' field as a list."""
        fm, _ = _parse_skill(skill_name)
        assert "allowed-tools" in fm, f"{skill_name} frontmatter missing 'allowed-tools'"
        assert isinstance(fm["allowed-tools"], list)
        assert len(fm["allowed-tools"]) > 0


# ===================================================================
# Domain keyword checks
# ===================================================================
class TestSkillDomainKeywords:
    """Skill content contains expected domain-specific keywords."""

    def test_wildlife_tracking_contains_iucn(self) -> None:
        """wildlife-tracking SKILL.md mentions IUCN."""
        _, body = _parse_skill("wildlife-tracking")
        assert "IUCN" in body, "wildlife-tracking SKILL.md should contain 'IUCN'"

    def test_fire_danger_contains_ffdi(self) -> None:
        """fire-danger-assessment SKILL.md mentions FFDI."""
        _, body = _parse_skill("fire-danger-assessment")
        assert "FFDI" in body, "fire-danger-assessment SKILL.md should contain 'FFDI'"

    def test_conservation_research_contains_keywords(self) -> None:
        """conservation-research SKILL.md mentions cross-reference or document categories."""
        _, body = _parse_skill("conservation-research")
        body_lower = body.lower()
        assert (
            "cross-reference" in body_lower or "cross-referencing" in body_lower or "document categories" in body_lower
        ), "conservation-research SKILL.md should contain 'cross-reference' or 'document categories'"

    def test_web_research_contains_bom(self) -> None:
        """web-research SKILL.md mentions bom.gov.au."""
        _, body = _parse_skill("web-research")
        assert "bom.gov.au" in body, "web-research SKILL.md should contain 'bom.gov.au'"
