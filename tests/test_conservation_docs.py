# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Unit tests for the Conservation Documents MCP server.

Tests services/mcp_servers/conservation_docs/server.py with mocked S3.
Covers list_documents, get_document, search_documents, and error handling.
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

# Ensure project root is on sys.path so models/ is importable
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from services.mcp_servers.conservation_docs.server import (
    get_document,
    list_documents,
    search_documents,
)

# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------
_PATCH_TARGET = "services.mcp_servers.conservation_docs.server._get_s3_client"


def _make_s3_object(key: str) -> dict[str, str]:
    """Build a minimal S3 object summary dict."""
    return {"Key": key}


def _make_body(content: str | bytes) -> MagicMock:
    """Create a mock S3 Body that supports .read()."""
    body = MagicMock()
    if isinstance(content, str):
        body.read.return_value = content.encode("utf-8")
    else:
        body.read.return_value = content
    return body


# ===================================================================
# list_documents
# ===================================================================
class TestListDocuments:
    """Tests for the list_documents tool."""

    def test_valid_category_returns_documents(self) -> None:
        """Valid category returns documents with metadata."""
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                _make_s3_object("species/"),
                _make_s3_object("species/koala.md"),
                _make_s3_object("species/platypus.md"),
            ],
        }
        with patch(_PATCH_TARGET, return_value=mock_s3):
            result = list_documents(category="species")

        assert result["count"] == 2
        assert len(result["documents"]) == 2
        assert result["documents"][0]["key"] == "species/koala.md"
        assert result["documents"][0]["category"] == "species"
        assert result["documents"][1]["key"] == "species/platypus.md"

    def test_invalid_category_returns_error(self) -> None:
        """Invalid category returns a validation error."""
        mock_s3 = MagicMock()
        with patch(_PATCH_TARGET, return_value=mock_s3):
            result = list_documents(category="invalid_category")

        assert result["error"] == "validation_error"
        assert "invalid_category" in result["message"]
        mock_s3.list_objects_v2.assert_not_called()

    def test_empty_category_returns_empty_list(self) -> None:
        """Category with no documents returns empty list."""
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.return_value = {
            "Contents": [_make_s3_object("emergency/")],
        }
        with patch(_PATCH_TARGET, return_value=mock_s3):
            result = list_documents(category="emergency")

        assert result["count"] == 0
        assert result["documents"] == []


# ===================================================================
# get_document
# ===================================================================
class TestGetDocument:
    """Tests for the get_document tool."""

    def test_markdown_returns_text_content(self) -> None:
        """Markdown file returns text content with text/markdown content_type."""
        mock_s3 = MagicMock()
        md_content = "# Koala\n\nKoalas are marsupials native to Australia."
        mock_s3.get_object.return_value = {"Body": _make_body(md_content)}

        with patch(_PATCH_TARGET, return_value=mock_s3):
            result = get_document(document_key="species/koala.md")

        assert result["key"] == "species/koala.md"
        assert result["content"] == md_content
        assert result["content_type"] == "text/markdown"

    def test_pdf_returns_base64_content(self) -> None:
        """PDF file returns base64-encoded content with application/pdf content_type."""
        mock_s3 = MagicMock()
        pdf_bytes = b"%PDF-1.4 fake pdf content"
        mock_s3.get_object.return_value = {"Body": _make_body(pdf_bytes)}

        with patch(_PATCH_TARGET, return_value=mock_s3):
            result = get_document(document_key="management_plans/plan.pdf")

        assert result["key"] == "management_plans/plan.pdf"
        assert result["content"] == base64.b64encode(pdf_bytes).decode("utf-8")
        assert result["content_type"] == "application/pdf"

    def test_missing_document_returns_not_found(self) -> None:
        """Missing document returns structured not_found error."""
        mock_s3 = MagicMock()
        error_response: dict[str, Any] = {
            "Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist."},
        }
        mock_s3.get_object.side_effect = ClientError(error_response, "GetObject")

        with patch(_PATCH_TARGET, return_value=mock_s3):
            result = get_document(document_key="species/nonexistent.md")

        assert result["error"] == "not_found"
        assert "nonexistent.md" in result["message"]
        assert result["document_key"] == "species/nonexistent.md"


# ===================================================================
# search_documents
# ===================================================================
class TestSearchDocuments:
    """Tests for the search_documents tool."""

    def _setup_paginator(self, mock_s3: MagicMock, objects: list[dict[str, str]]) -> None:
        """Configure mock paginator to return the given objects."""
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"Contents": objects}]
        mock_s3.get_paginator.return_value = mock_paginator

    def test_keyword_match_returns_results(self) -> None:
        """Keyword match returns matching documents with excerpts."""
        mock_s3 = MagicMock()
        self._setup_paginator(
            mock_s3,
            [
                _make_s3_object("species/koala.md"),
                _make_s3_object("species/platypus.md"),
            ],
        )
        mock_s3.get_object.side_effect = [
            {"Body": _make_body("The koala is a marsupial found in eucalyptus forests.")},
            {"Body": _make_body("The platypus is a monotreme found in freshwater streams.")},
        ]

        with patch(_PATCH_TARGET, return_value=mock_s3):
            result = search_documents(keyword="eucalyptus")

        assert result["count"] == 1
        assert result["results"][0]["key"] == "species/koala.md"
        assert "excerpt" in result["results"][0]

    def test_no_matches_returns_empty(self) -> None:
        """No keyword matches returns empty results."""
        mock_s3 = MagicMock()
        self._setup_paginator(mock_s3, [_make_s3_object("species/koala.md")])
        mock_s3.get_object.return_value = {
            "Body": _make_body("The koala is a marsupial."),
        }

        with patch(_PATCH_TARGET, return_value=mock_s3):
            result = search_documents(keyword="dinosaur")

        assert result["count"] == 0
        assert result["results"] == []

    def test_skips_pdf_files(self) -> None:
        """PDF files are skipped during content search."""
        mock_s3 = MagicMock()
        self._setup_paginator(
            mock_s3,
            [
                _make_s3_object("species/koala.md"),
                _make_s3_object("management_plans/plan.pdf"),
            ],
        )
        # Only the markdown file should trigger get_object
        mock_s3.get_object.return_value = {
            "Body": _make_body("The koala is a marsupial found in eucalyptus forests."),
        }

        with patch(_PATCH_TARGET, return_value=mock_s3):
            result = search_documents(keyword="koala")

        assert result["count"] == 1
        assert result["results"][0]["key"] == "species/koala.md"
        # get_object should only be called once (for the .md file, not the .pdf)
        assert mock_s3.get_object.call_count == 1
