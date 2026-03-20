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

from models.documents import CATEGORIES
from services.mcp_servers.conservation_docs.server import (
    _parse_s3_uri,
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
            result = search_documents(query=keyword)

        matched_keys = [r["key"] for r in result["results"]]
        assert document_key in matched_keys, (
            f"Document '{document_key}' containing keyword '{keyword}' was not found in search results: {matched_keys}"
        )


# ===================================================================
# Bedrock Knowledge Base feature — Property-based tests (P5–P8)
# ===================================================================

_BEDROCK_CLIENT_PATCH = "services.mcp_servers.conservation_docs.server._get_bedrock_agent_runtime_client"
_KB_ID_PATCH = "services.mcp_servers.conservation_docs.server._KNOWLEDGE_BASE_ID"

# Strategies for bedrock-knowledge-base properties
_query_st = st.text(min_size=1, max_size=50)
_score_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
_text_passage_st = st.text(min_size=1, max_size=200)


# ===================================================================
# Property 5: Semantic search returns correctly structured results
# ===================================================================
class TestBedrockKBProperty5SemanticSearchStructure:
    """Feature: bedrock-knowledge-base, Property 5: Semantic search returns correctly structured results."""

    @settings(max_examples=100, database=None)
    @given(
        query=_query_st,
        categories=st.lists(
            st.sampled_from(list(CATEGORIES)),
            min_size=1,
            max_size=5,
        ),
        filenames=st.lists(
            st.text(
                min_size=1,
                max_size=20,
                alphabet=st.characters(whitelist_categories=("L", "N")),
            ),
            min_size=1,
            max_size=5,
        ),
        scores=st.lists(_score_st, min_size=1, max_size=5),
        texts=st.lists(_text_passage_st, min_size=1, max_size=5),
    )
    def test_results_have_required_fields(
        self,
        query: str,
        categories: list[str],
        filenames: list[str],
        scores: list[float],
        texts: list[str],
    ) -> None:
        """Feature: bedrock-knowledge-base, Property 5: Semantic search returns correctly structured results.

        For any query and mocked Bedrock retrieval response, each result
        returned by search_documents contains source_uri, document_key,
        category, text, and score fields.

        **Validates: Requirements 2.1, 2.2**
        """
        # Build mock retrieval results — zip to shortest list
        n = min(len(categories), len(filenames), len(scores), len(texts))
        retrieval_results = []
        for i in range(n):
            cat = categories[i]
            fname = filenames[i]
            uri = f"s3://bush-ranger-docs-123456789012-us-east-1/{cat}/{fname}.md"
            retrieval_results.append(
                {
                    "content": {"text": texts[i]},
                    "location": {
                        "type": "S3",
                        "s3Location": {"uri": uri},
                    },
                    "score": scores[i],
                }
            )

        mock_client = MagicMock()
        mock_client.retrieve.return_value = {"retrievalResults": retrieval_results}

        with (
            patch(_BEDROCK_CLIENT_PATCH, return_value=mock_client),
            patch(_KB_ID_PATCH, "kb-test-id"),
        ):
            result = search_documents(query=query)

        assert "results" in result
        assert "count" in result
        assert result["count"] == len(result["results"])

        required_fields = {"source_uri", "document_key", "category", "text", "score"}
        for item in result["results"]:
            assert required_fields.issubset(item.keys()), f"Missing fields: {required_fields - item.keys()}"


# ===================================================================
# Property 6: S3 URI parsing round-trip
# ===================================================================
class TestBedrockKBProperty6S3URIParsingRoundTrip:
    """Feature: bedrock-knowledge-base, Property 6: S3 URI parsing round-trip."""

    @settings(max_examples=100, database=None)
    @given(
        category=st.sampled_from(list(CATEGORIES)),
        filename=st.text(
            min_size=1,
            max_size=30,
            alphabet=st.characters(whitelist_categories=("L", "N")),
        ),
    )
    def test_parse_s3_uri_recovers_key_and_category(
        self,
        category: str,
        filename: str,
    ) -> None:
        """Feature: bedrock-knowledge-base, Property 6: S3 URI parsing round-trip.

        For any valid (category, filename) pair, building an S3 URI and
        parsing it with _parse_s3_uri recovers the original object key
        and category.

        **Validates: Requirements 2.3**
        """
        object_key = f"{category}/{filename}.md"
        uri = f"s3://bush-ranger-docs-123456789012-us-east-1/{object_key}"

        parsed_key, parsed_category = _parse_s3_uri(uri)

        assert parsed_key == object_key, f"Expected key {object_key!r}, got {parsed_key!r}"
        assert parsed_category == category, f"Expected category {category!r}, got {parsed_category!r}"


# ===================================================================
# Property 7: max_results parameter clamping
# ===================================================================
class TestBedrockKBProperty7MaxResultsClamping:
    """Feature: bedrock-knowledge-base, Property 7: max_results parameter clamping."""

    @settings(max_examples=100, database=None)
    @given(
        max_results=st.integers(min_value=-1000, max_value=1000),
    )
    def test_max_results_clamped_to_valid_range(
        self,
        max_results: int,
    ) -> None:
        """Feature: bedrock-knowledge-base, Property 7: max_results parameter clamping.

        For any integer max_results, the numberOfResults passed to the
        Bedrock retrieve API is clamped to [1, 20].

        **Validates: Requirements 2.4**
        """
        mock_client = MagicMock()
        mock_client.retrieve.return_value = {"retrievalResults": []}

        with (
            patch(_BEDROCK_CLIENT_PATCH, return_value=mock_client),
            patch(_KB_ID_PATCH, "kb-test-id"),
        ):
            search_documents(query="test", max_results=max_results)

        mock_client.retrieve.assert_called_once()
        call_kwargs = mock_client.retrieve.call_args
        number_of_results = (
            call_kwargs.kwargs.get("retrievalConfiguration", {})
            .get("vectorSearchConfiguration", {})
            .get("numberOfResults")
        )
        if number_of_results is None:
            # Try positional/keyword args
            number_of_results = (
                call_kwargs[1]
                .get("retrievalConfiguration", {})
                .get("vectorSearchConfiguration", {})
                .get("numberOfResults")
            )

        assert number_of_results is not None, "numberOfResults not passed to retrieve()"
        assert 1 <= number_of_results <= 20, (
            f"numberOfResults={number_of_results} is outside [1, 20] for input max_results={max_results}"
        )

    def test_default_max_results_is_5(self) -> None:
        """Feature: bedrock-knowledge-base, Property 7: max_results parameter clamping.

        When max_results is not specified, the default value of 5 is used.

        **Validates: Requirements 2.4**
        """
        mock_client = MagicMock()
        mock_client.retrieve.return_value = {"retrievalResults": []}

        with (
            patch(_BEDROCK_CLIENT_PATCH, return_value=mock_client),
            patch(_KB_ID_PATCH, "kb-test-id"),
        ):
            search_documents(query="test")

        call_kwargs = mock_client.retrieve.call_args
        number_of_results = (
            call_kwargs.kwargs.get("retrievalConfiguration", {})
            .get("vectorSearchConfiguration", {})
            .get("numberOfResults")
        )
        if number_of_results is None:
            number_of_results = (
                call_kwargs[1]
                .get("retrievalConfiguration", {})
                .get("vectorSearchConfiguration", {})
                .get("numberOfResults")
            )

        assert number_of_results == 5, f"Default numberOfResults should be 5, got {number_of_results}"


# ===================================================================
# Property 8: Fallback to substring matching without Knowledge Base ID
# ===================================================================
class TestBedrockKBProperty8FallbackWithoutKBID:
    """Feature: bedrock-knowledge-base, Property 8: Fallback to substring matching without Knowledge Base ID."""

    @settings(max_examples=100, database=None)
    @given(
        query=_query_st,
    )
    def test_fallback_uses_s3_not_bedrock(
        self,
        query: str,
    ) -> None:
        """Feature: bedrock-knowledge-base, Property 8: Fallback to substring matching without Knowledge Base ID.

        When KNOWLEDGE_BASE_ID is not set, search_documents uses S3
        (via paginator) and does NOT call Bedrock retrieve.

        **Validates: Requirements 5.2**
        """
        mock_s3 = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"Contents": []}]
        mock_s3.get_paginator.return_value = mock_paginator

        mock_bedrock = MagicMock()

        with (
            patch(_PATCH_TARGET, return_value=mock_s3),
            patch(_BEDROCK_CLIENT_PATCH, return_value=mock_bedrock),
            patch(_KB_ID_PATCH, None),
        ):
            result = search_documents(query=query)

        # S3 paginator should have been called
        mock_s3.get_paginator.assert_called_once_with("list_objects_v2")

        # Bedrock retrieve should NOT have been called
        mock_bedrock.retrieve.assert_not_called()

        # Result should still have the expected structure
        assert "results" in result
        assert "count" in result
