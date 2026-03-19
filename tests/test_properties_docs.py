# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Property-based tests for the Conservation Documents MCP server.

Uses hypothesis to verify correctness properties across randomised inputs.
Tests services/mcp_servers/conservation_docs/server.py with mocked S3.
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

# Ensure project root is on sys.path so models/ is importable
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from services.mcp_servers.conservation_docs.server import (
    get_document,
    search_documents,
)

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------
_PATCH_TARGET = "services.mcp_servers.conservation_docs.server._get_s3_client"

_content_st = st.text(min_size=1, max_size=200)
_category_st = st.sampled_from(["species", "management_plans", "emergency"])
_filename_st = st.text(
    min_size=1,
    max_size=30,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)


# ===================================================================
# Property 7: Document Round-Trip
# ===================================================================
class TestProperty7DocumentRoundTrip:
    """Feature: aws-agentcore-mcp-infrastructure, Property 7: Document Round-Trip."""

    @settings(max_examples=100, database=None)
    @given(
        content=_content_st,
        category=_category_st,
        filename=_filename_st,
    )
    def test_markdown_round_trip(
        self,
        content: str,
        category: str,
        filename: str,
    ) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 7: Document Round-Trip.

        For any markdown document content uploaded to S3, retrieving it by key
        via get_document returns content identical to the original (text path).

        **Validates: Requirements 2.2**
        """
        document_key = f"{category}/{filename}.md"

        mock_s3 = MagicMock()
        body = MagicMock()
        body.read.return_value = content.encode("utf-8")
        mock_s3.get_object.return_value = {"Body": body}

        with patch(_PATCH_TARGET, return_value=mock_s3):
            result = get_document(document_key=document_key)

        assert result["key"] == document_key
        assert result["content"] == content, f"Round-trip failed: expected {content!r}, got {result['content']!r}"
        assert result["content_type"] == "text/markdown"

    @settings(max_examples=100, database=None)
    @given(
        content=st.binary(min_size=1, max_size=200),
        category=_category_st,
        filename=_filename_st,
    )
    def test_pdf_round_trip(
        self,
        content: bytes,
        category: str,
        filename: str,
    ) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 7: Document Round-Trip.

        For any PDF document content uploaded to S3, retrieving it by key
        via get_document returns base64-encoded content identical to the original.

        **Validates: Requirements 2.2**
        """
        document_key = f"{category}/{filename}.pdf"

        mock_s3 = MagicMock()
        body = MagicMock()
        body.read.return_value = content
        mock_s3.get_object.return_value = {"Body": body}

        with patch(_PATCH_TARGET, return_value=mock_s3):
            result = get_document(document_key=document_key)

        assert result["key"] == document_key
        expected_b64 = base64.b64encode(content).decode("utf-8")
        assert result["content"] == expected_b64, "Round-trip failed: base64 content does not match original bytes"
        assert result["content_type"] == "application/pdf"


# ===================================================================
# Property 8: Search Matches Content
# ===================================================================
class TestProperty8SearchMatchesContent:
    """Feature: aws-agentcore-mcp-infrastructure, Property 8: Search Matches Content."""

    @settings(max_examples=100, database=None)
    @given(
        keyword=st.text(
            min_size=1,
            max_size=30,
            alphabet=st.characters(whitelist_categories=("L", "N")),
        ),
        prefix_text=_content_st,
        suffix_text=_content_st,
        category=_category_st,
        filename=_filename_st,
    )
    def test_search_finds_document_containing_keyword(
        self,
        keyword: str,
        prefix_text: str,
        suffix_text: str,
        category: str,
        filename: str,
    ) -> None:
        """Feature: aws-agentcore-mcp-infrastructure, Property 8: Search Matches Content.

        For any document containing keyword K, searching with keyword K includes
        that document in the results.

        **Validates: Requirements 2.5**
        """
        document_key = f"{category}/{filename}.md"
        document_content = f"{prefix_text} {keyword} {suffix_text}"

        mock_s3 = MagicMock()

        # Mock paginator
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"Contents": [{"Key": document_key}]},
        ]
        mock_s3.get_paginator.return_value = mock_paginator

        # Mock get_object for content retrieval during search
        body = MagicMock()
        body.read.return_value = document_content.encode("utf-8")
        mock_s3.get_object.return_value = {"Body": body}

        with patch(_PATCH_TARGET, return_value=mock_s3):
            result = search_documents(keyword=keyword)

        matched_keys = [r["key"] for r in result["results"]]
        assert document_key in matched_keys, (
            f"Document '{document_key}' containing keyword '{keyword}' was not found in search results: {matched_keys}"
        )
