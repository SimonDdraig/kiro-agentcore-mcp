# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Tests for metadata sidecar file validation.

Feature: bedrock-knowledge-base, Property 9: Metadata sidecar files are valid and complete
Validates: Requirements 7.1, 7.2, 7.4, 10.1, 10.2
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from models.documents import CATEGORIES

SAMPLE_DOCS_DIR = Path("config/sample_documents")


def _collect_md_files() -> list[Path]:
    """Walk sample_documents and return all .md files."""
    md_files: list[Path] = []
    for root, _dirs, files in os.walk(SAMPLE_DOCS_DIR):
        for f in files:
            if f.endswith(".md"):
                md_files.append(Path(root) / f)
    return md_files


def _collect_sidecar_files() -> list[Path]:
    """Walk sample_documents and return all .metadata.json sidecar files."""
    sidecars: list[Path] = []
    for root, _dirs, files in os.walk(SAMPLE_DOCS_DIR):
        for f in files:
            if f.endswith(".metadata.json"):
                sidecars.append(Path(root) / f)
    return sidecars


class TestMetadataSidecarFiles:
    """Validate that every sample document has a correct metadata sidecar."""

    def test_every_document_has_metadata_sidecar(self) -> None:
        """Every .md file in config/sample_documents/ must have a .metadata.json sidecar."""
        md_files = _collect_md_files()
        assert md_files, "Expected at least one .md file in sample_documents"

        missing: list[str] = []
        for md_path in md_files:
            sidecar = md_path.parent / f"{md_path.name}.metadata.json"
            if not sidecar.exists():
                missing.append(str(md_path))

        assert not missing, f"Missing metadata sidecars for: {missing}"

    def test_metadata_category_matches_folder(self) -> None:
        """Each sidecar's metadataAttributes.category.value must equal the parent folder name."""
        sidecars = _collect_sidecar_files()
        assert sidecars, "Expected at least one .metadata.json sidecar"

        mismatches: list[str] = []
        for sidecar_path in sidecars:
            folder_name = sidecar_path.parent.name
            with open(sidecar_path) as f:
                data = json.load(f)

            category_value = data["metadataAttributes"]["category"]["value"]
            if category_value != folder_name:
                mismatches.append(f"{sidecar_path}: expected category '{folder_name}', got '{category_value}'")

        assert not mismatches, "Category mismatches:\n" + "\n".join(mismatches)

    def test_metadata_conforms_to_bedrock_format(self) -> None:
        """Each sidecar must have metadataAttributes with category containing value and type fields."""
        sidecars = _collect_sidecar_files()
        assert sidecars, "Expected at least one .metadata.json sidecar"

        errors: list[str] = []
        for sidecar_path in sidecars:
            with open(sidecar_path) as f:
                data = json.load(f)

            attrs = data.get("metadataAttributes")
            if attrs is None:
                errors.append(f"{sidecar_path}: missing 'metadataAttributes' key")
                continue

            category = attrs.get("category")
            if category is None:
                errors.append(f"{sidecar_path}: missing 'category' in metadataAttributes")
                continue

            if "value" not in category:
                errors.append(f"{sidecar_path}: category missing 'value' field")
            if "type" not in category:
                errors.append(f"{sidecar_path}: category missing 'type' field")
            elif category["type"] != "STRING":
                errors.append(f"{sidecar_path}: category type is '{category['type']}', expected 'STRING'")

            # Verify category value is a valid category
            if "value" in category and category["value"] not in CATEGORIES:
                errors.append(f"{sidecar_path}: category value '{category['value']}' not in {CATEGORIES}")

        assert not errors, "Bedrock format errors:\n" + "\n".join(errors)
