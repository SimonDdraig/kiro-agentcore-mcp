# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Property-based tests for copyright header compliance.

Uses hypothesis to verify that all Python and TypeScript source files
in the project begin with the correct copyright header comment.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

_PYTHON_COPYRIGHT = "# Copyright 2025 Bush Ranger AI Project. All rights reserved."
_TYPESCRIPT_COPYRIGHT = "// Copyright 2025 Bush Ranger AI Project. All rights reserved."

_EXCLUDED_DIRS = {
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    "bush-ranger-venv",
    "node_modules",
    ".git",
    ".hypothesis",
    ".pytest_cache",
    ".vscode",
}


def _should_exclude(path: Path) -> bool:
    """Return True if any part of the path is in the excluded directories."""
    return any(part in _EXCLUDED_DIRS for part in path.parts)


def _discover_python_files() -> list[Path]:
    """Discover all .py files in the project, excluding vendored/generated dirs."""
    return [p for p in _PROJECT_ROOT.rglob("*.py") if not _should_exclude(p.relative_to(_PROJECT_ROOT))]


def _discover_typescript_files() -> list[Path]:
    """Discover all .ts and .tsx files under frontend/src/."""
    frontend_src = _PROJECT_ROOT / "frontend" / "src"
    if not frontend_src.exists():
        return []
    ts_files: list[Path] = []
    for ext in ("*.ts", "*.tsx"):
        ts_files.extend(p for p in frontend_src.rglob(ext) if not _should_exclude(p.relative_to(_PROJECT_ROOT)))
    return ts_files


# Discover files once at module load so hypothesis can sample from them.
_PYTHON_FILES = _discover_python_files()
_TYPESCRIPT_FILES = _discover_typescript_files()


# ===================================================================
# Property 18: All Source Files Contain Copyright Header
# ===================================================================
class TestProperty18CopyrightHeader:
    """Feature: aws-agentcore-mcp-infrastructure, Property 18: All Source Files Contain Copyright Header."""

    @pytest.mark.skipif(not _PYTHON_FILES, reason="No Python files found")
    @settings(max_examples=100, database=None)
    @given(py_file=st.sampled_from(_PYTHON_FILES) if _PYTHON_FILES else st.nothing())
    def test_python_files_have_copyright_header(self, py_file: Path) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 18: All Source Files Contain Copyright Header.

        For any Python (.py) source file in the project, the file SHALL begin
        with the copyright header comment.

        **Validates: Requirements 15.5**
        """
        content = py_file.read_text(encoding="utf-8")
        first_line = content.split("\n", maxsplit=1)[0]
        assert first_line == _PYTHON_COPYRIGHT, (
            f"File {py_file.relative_to(_PROJECT_ROOT)} does not start with copyright header.\n"
            f"  Expected: {_PYTHON_COPYRIGHT}\n"
            f"  Got:      {first_line!r}"
        )

    @pytest.mark.skipif(not _TYPESCRIPT_FILES, reason="No TypeScript files found")
    @settings(max_examples=100, database=None)
    @given(ts_file=st.sampled_from(_TYPESCRIPT_FILES) if _TYPESCRIPT_FILES else st.nothing())
    def test_typescript_files_have_copyright_header(self, ts_file: Path) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 18: All Source Files Contain Copyright Header.

        For any TypeScript (.ts, .tsx) source file in the project, the file SHALL
        begin with the copyright header comment.

        **Validates: Requirements 15.5**
        """
        content = ts_file.read_text(encoding="utf-8")
        first_line = content.split("\n", maxsplit=1)[0]
        assert first_line == _TYPESCRIPT_COPYRIGHT, (
            f"File {ts_file.relative_to(_PROJECT_ROOT)} does not start with copyright header.\n"
            f"  Expected: {_TYPESCRIPT_COPYRIGHT}\n"
            f"  Got:      {first_line!r}"
        )
