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
            result = search_documents(query="eucalyptus")

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
            result = search_documents(query="dinosaur")

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
            result = search_documents(query="koala")

        assert result["count"] == 1
        assert result["results"][0]["key"] == "species/koala.md"
        # get_object should only be called once (for the .md file, not the .pdf)
        assert mock_s3.get_object.call_count == 1


# ===================================================================
# Semantic search (Bedrock Knowledge Base)
# ===================================================================
_PATCH_BEDROCK = "services.mcp_servers.conservation_docs.server._get_bedrock_agent_runtime_client"
_PATCH_KB_ID = "services.mcp_servers.conservation_docs.server._KNOWLEDGE_BASE_ID"


def _make_retrieval_result(
    uri: str = "s3://bush-ranger-docs-123456789012-us-east-1/species/koala.md",
    text: str = "Koalas are marsupials native to Australia.",
    score: float = 0.87,
) -> dict[str, Any]:
    """Build a single Bedrock retrievalResults entry."""
    return {
        "content": {"text": text},
        "location": {"type": "S3", "s3Location": {"uri": uri}},
        "score": score,
    }


class TestSemanticSearch:
    """Tests for the Bedrock Knowledge Base semantic search path."""

    def test_semantic_search_returns_structured_results(self) -> None:
        """Semantic search returns results with required fields."""
        mock_bedrock = MagicMock()
        mock_bedrock.retrieve.return_value = {
            "retrievalResults": [
                _make_retrieval_result(
                    uri="s3://bucket/species/koala.md",
                    text="Koalas eat eucalyptus.",
                    score=0.92,
                ),
                _make_retrieval_result(
                    uri="s3://bucket/emergency/bushfire_response.md",
                    text="Bushfire emergency procedures.",
                    score=0.78,
                ),
            ],
        }

        with (
            patch(_PATCH_BEDROCK, return_value=mock_bedrock),
            patch(_PATCH_KB_ID, "kb-test-id"),
        ):
            result = search_documents(query="koala habitat")

        assert result["count"] == 2
        assert len(result["results"]) == 2

        first = result["results"][0]
        assert first["source_uri"] == "s3://bucket/species/koala.md"
        assert first["document_key"] == "species/koala.md"
        assert first["category"] == "species"
        assert first["text"] == "Koalas eat eucalyptus."
        assert first["score"] == 0.92

        second = result["results"][1]
        assert second["source_uri"] == "s3://bucket/emergency/bushfire_response.md"
        assert second["document_key"] == "emergency/bushfire_response.md"
        assert second["category"] == "emergency"

    def test_search_returns_structured_error_on_client_error(self) -> None:
        """Bedrock ClientError returns structured error dict."""
        mock_bedrock = MagicMock()
        mock_bedrock.retrieve.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Not authorized"}},
            "Retrieve",
        )

        with (
            patch(_PATCH_BEDROCK, return_value=mock_bedrock),
            patch(_PATCH_KB_ID, "kb-test-id"),
        ):
            result = search_documents(query="koala")

        assert result["error"] == "retrieval_error"
        assert "message" in result
        assert "Failed to retrieve" in result["message"]

    def test_fallback_logs_warning_when_kb_id_missing(self) -> None:
        """When _KNOWLEDGE_BASE_ID is None, a warning is logged."""
        mock_s3 = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"Contents": []}]
        mock_s3.get_paginator.return_value = mock_paginator

        with (
            patch(_PATCH_TARGET, return_value=mock_s3),
            patch(_PATCH_KB_ID, None),
            patch("services.mcp_servers.conservation_docs.server.logger") as mock_logger,
        ):
            search_documents(query="koala")

        mock_logger.warning.assert_called_once()
        assert "KNOWLEDGE_BASE_ID" in mock_logger.warning.call_args[0][0]

    def test_list_and_get_do_not_use_bedrock(self) -> None:
        """list_documents and get_document never call the Bedrock client."""
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.return_value = {
            "Contents": [_make_s3_object("species/"), _make_s3_object("species/koala.md")],
        }
        mock_s3.get_object.return_value = {"Body": _make_body("# Koala")}

        mock_bedrock = MagicMock()

        with (
            patch(_PATCH_TARGET, return_value=mock_s3),
            patch(_PATCH_BEDROCK, return_value=mock_bedrock),
        ):
            list_documents(category="species")
            get_document(document_key="species/koala.md")

        mock_bedrock.retrieve.assert_not_called()

    def test_unparseable_uri_skipped(self) -> None:
        """Results with unparseable S3 URIs are skipped."""
        mock_bedrock = MagicMock()
        # Use a result where the uri value is None (causes _parse_s3_uri to raise)
        # alongside a valid result to verify only the valid one is returned.
        mock_bedrock.retrieve.return_value = {
            "retrievalResults": [
                {
                    "content": {"text": "bad result"},
                    "location": {"s3Location": {"uri": None}},
                    "score": 0.5,
                },
                _make_retrieval_result(
                    uri="s3://bucket/species/platypus.md",
                    text="Platypus info.",
                    score=0.8,
                ),
            ],
        }

        with (
            patch(_PATCH_BEDROCK, return_value=mock_bedrock),
            patch(_PATCH_KB_ID, "kb-test-id"),
        ):
            result = search_documents(query="platypus")

        # Only the valid result should be present
        assert result["count"] == 1
        assert result["results"][0]["document_key"] == "species/platypus.md"

    def test_empty_retrieval_results(self) -> None:
        """Empty retrievalResults returns {"results": [], "count": 0}."""
        mock_bedrock = MagicMock()
        mock_bedrock.retrieve.return_value = {"retrievalResults": []}

        with (
            patch(_PATCH_BEDROCK, return_value=mock_bedrock),
            patch(_PATCH_KB_ID, "kb-test-id"),
        ):
            result = search_documents(query="anything")

        assert result == {"results": [], "count": 0}


# ===================================================================
# Category filter in search_documents
# ===================================================================


class TestCategoryFilter:
    """Tests for the optional category filter in search_documents."""

    def test_search_with_valid_category_passes_metadata_filter(self) -> None:
        """Providing a valid category passes a metadata filter to Bedrock retrieve.

        Validates: Requirements 9.1, 10.3
        """
        mock_bedrock = MagicMock()
        mock_bedrock.retrieve.return_value = {
            "retrievalResults": [
                _make_retrieval_result(
                    uri="s3://bucket/species/koala.md",
                    text="Koalas eat eucalyptus.",
                    score=0.92,
                ),
            ],
        }

        with (
            patch(_PATCH_BEDROCK, return_value=mock_bedrock),
            patch(_PATCH_KB_ID, "kb-test-id"),
        ):
            result = search_documents(query="koala", category="species")

        # Verify the retrieve call included the metadata filter
        mock_bedrock.retrieve.assert_called_once()
        call_kwargs = mock_bedrock.retrieve.call_args[1]
        vector_config = call_kwargs["retrievalConfiguration"]["vectorSearchConfiguration"]
        assert "filter" in vector_config
        assert vector_config["filter"] == {
            "equals": {
                "key": "category",
                "value": "species",
            }
        }

        # Verify results are still returned correctly
        assert result["count"] == 1
        assert result["results"][0]["category"] == "species"

    def test_search_without_category_no_filter(self) -> None:
        """Omitting category performs unfiltered search (no filter key).

        Validates: Requirements 9.2, 10.4
        """
        mock_bedrock = MagicMock()
        mock_bedrock.retrieve.return_value = {
            "retrievalResults": [
                _make_retrieval_result(
                    uri="s3://bucket/species/koala.md",
                    text="Koalas eat eucalyptus.",
                    score=0.92,
                ),
            ],
        }

        with (
            patch(_PATCH_BEDROCK, return_value=mock_bedrock),
            patch(_PATCH_KB_ID, "kb-test-id"),
        ):
            result = search_documents(query="koala")

        # Verify the retrieve call did NOT include a filter key
        mock_bedrock.retrieve.assert_called_once()
        call_kwargs = mock_bedrock.retrieve.call_args[1]
        vector_config = call_kwargs["retrievalConfiguration"]["vectorSearchConfiguration"]
        assert "filter" not in vector_config

        # Verify results are still returned
        assert result["count"] == 1

    def test_search_invalid_category_returns_validation_error(self) -> None:
        """Providing an invalid category returns a validation error without calling Bedrock.

        Validates: Requirements 9.3, 10.3
        """
        mock_bedrock = MagicMock()

        with (
            patch(_PATCH_BEDROCK, return_value=mock_bedrock),
            patch(_PATCH_KB_ID, "kb-test-id"),
        ):
            result = search_documents(query="koala", category="invalid")

        assert result["error"] == "validation_error"
        assert "invalid" in result["message"]
        assert "species" in result["message"]
        assert "management_plans" in result["message"]
        assert "emergency" in result["message"]

        # Bedrock should NOT have been called
        mock_bedrock.retrieve.assert_not_called()
