# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Conservation Documents MCP server — S3-backed tools for document retrieval and search."""

from __future__ import annotations

import base64
import logging
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError
from mcp.server.fastmcp import FastMCP

from models.documents import CATEGORIES, DOCS_BUCKET_PREFIX, DocumentMetadata

# ---------------------------------------------------------------------------
# MCP server instance
# ---------------------------------------------------------------------------
mcp = FastMCP("conservation-docs")

# ---------------------------------------------------------------------------
# Module-level configuration
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

_KNOWLEDGE_BASE_ID = os.environ.get("KNOWLEDGE_BASE_ID")

# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------
_BUCKET_NAME = os.environ.get("DOCS_BUCKET_NAME", DOCS_BUCKET_PREFIX)


def _get_s3_client() -> Any:
    """Return a boto3 S3 client."""
    return boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def _object_to_metadata(key: str) -> DocumentMetadata:
    """Convert an S3 object key into a DocumentMetadata instance."""
    parts = key.split("/", 1)
    category = parts[0] if parts[0] in CATEGORIES else "unknown"
    filename = parts[1] if len(parts) > 1 else parts[0]
    title = os.path.splitext(filename)[0].replace("_", " ").replace("-", " ").title()
    return DocumentMetadata(key=key, title=title, category=category)


def _metadata_to_dict(meta: DocumentMetadata) -> dict[str, str]:
    """Convert a DocumentMetadata to a plain dict for JSON serialisation."""
    return {"key": meta.key, "title": meta.title, "category": meta.category}


def _not_found_error(document_key: str) -> dict[str, Any]:
    """Return a structured 'not found' error for a missing document."""
    return {
        "error": "not_found",
        "message": f"Document not found: {document_key}",
        "document_key": document_key,
    }


# ---------------------------------------------------------------------------
# Bedrock helpers
# ---------------------------------------------------------------------------


def _get_bedrock_agent_runtime_client() -> Any:
    """Return a boto3 Bedrock Agent Runtime client."""
    return boto3.client("bedrock-agent-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    """Extract (object_key, category) from an S3 URI.

    Example:
        >>> _parse_s3_uri("s3://bush-ranger-docs-123456789012-us-east-1/species/koala.md")
        ("species/koala.md", "species")
    """
    # Strip the "s3://bucket-name/" prefix to get the object key
    without_scheme = uri.removeprefix("s3://")
    # The first segment after the scheme is the bucket name
    _, _, object_key = without_scheme.partition("/")
    # The category is the first path segment of the object key
    category = object_key.split("/", 1)[0]
    return object_key, category


# ---------------------------------------------------------------------------
# Fallback search (substring matching)
# ---------------------------------------------------------------------------


def _fallback_search(query: str) -> dict[str, Any]:
    """Perform substring-matching search across all documents in the bucket.

    This is the legacy search behaviour used when no Knowledge Base is configured.
    """
    s3 = _get_s3_client()
    keyword_lower = query.lower()

    # List all objects across every category
    all_objects: list[dict[str, Any]] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=_BUCKET_NAME):
        all_objects.extend(page.get("Contents", []))

    results: list[dict[str, Any]] = []
    for obj in all_objects:
        key: str = obj["Key"]

        # Skip directory markers and non-text files
        if key.endswith("/") or key.lower().endswith(".pdf"):
            continue

        try:
            resp = s3.get_object(Bucket=_BUCKET_NAME, Key=key)
            text = resp["Body"].read().decode("utf-8")
        except (ClientError, UnicodeDecodeError):
            continue

        if keyword_lower in text.lower():
            meta = _object_to_metadata(key)
            # Build a short excerpt around the first match
            idx = text.lower().index(keyword_lower)
            start = max(0, idx - 80)
            end = min(len(text), idx + len(query) + 80)
            excerpt = text[start:end].replace("\n", " ").strip()
            if start > 0:
                excerpt = "..." + excerpt
            if end < len(text):
                excerpt = excerpt + "..."

            result = _metadata_to_dict(meta)
            result["excerpt"] = excerpt
            results.append(result)

    return {"results": results, "count": len(results)}


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_documents(category: str) -> dict[str, Any]:
    """List conservation documents filtered by category.

    Args:
        category: Document category — one of 'species',
            'management_plans', or 'emergency'.

    Returns:
        A dict with a 'documents' list of document metadata and a 'count'.
    """
    if category not in CATEGORIES:
        return {
            "error": "validation_error",
            "message": f"Invalid category '{category}'. Must be one of: {', '.join(CATEGORIES)}",
        }

    s3 = _get_s3_client()
    prefix = f"{category}/"

    response = s3.list_objects_v2(Bucket=_BUCKET_NAME, Prefix=prefix)
    contents = response.get("Contents", [])

    documents: list[dict[str, str]] = []
    for obj in contents:
        key: str = obj["Key"]
        # Skip the prefix-only entry (directory marker)
        if key == prefix:
            continue
        meta = _object_to_metadata(key)
        documents.append(_metadata_to_dict(meta))

    return {"documents": documents, "count": len(documents)}


@mcp.tool()
def get_document(document_key: str) -> dict[str, Any]:
    """Retrieve a conservation document by its S3 key.

    Markdown files are returned as plain text. PDF files are returned as
    base64-encoded strings.

    Args:
        document_key: The S3 object key, e.g. 'species/koala.md'.

    Returns:
        A dict with 'key', 'content', and 'content_type', or a structured
        error if the document is not found.
    """
    s3 = _get_s3_client()

    try:
        response = s3.get_object(Bucket=_BUCKET_NAME, Key=document_key)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code in ("NoSuchKey", "404"):
            return _not_found_error(document_key)
        raise

    body_bytes: bytes = response["Body"].read()

    if document_key.lower().endswith(".pdf"):
        content = base64.b64encode(body_bytes).decode("utf-8")
        content_type = "application/pdf"
    else:
        content = body_bytes.decode("utf-8")
        content_type = "text/markdown"

    return {
        "key": document_key,
        "content": content,
        "content_type": content_type,
    }


@mcp.tool()
def search_documents(query: str, max_results: int = 5) -> dict[str, Any]:
    """Search conservation documents by semantic query.

    When a Knowledge Base is configured, performs semantic search via the
    Bedrock ``retrieve`` API.  Otherwise falls back to legacy substring
    matching against S3 document content.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return (default 5,
            clamped to [1, 20]).

    Returns:
        A dict with 'results' and 'count', or a structured error dict.
    """
    clamped_max_results = max(1, min(max_results, 20))

    if not _KNOWLEDGE_BASE_ID:
        logger.warning("KNOWLEDGE_BASE_ID is not set — falling back to substring search.")
        return _fallback_search(query)

    try:
        client = _get_bedrock_agent_runtime_client()
        response = client.retrieve(
            knowledgeBaseId=_KNOWLEDGE_BASE_ID,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {
                    "numberOfResults": clamped_max_results,
                }
            },
        )
    except ClientError as exc:
        return {
            "error": "retrieval_error",
            "message": f"Failed to retrieve from Knowledge Base: {exc}",
        }

    retrieval_results = response.get("retrievalResults", [])
    if not retrieval_results:
        return {"results": [], "count": 0}

    results: list[dict[str, Any]] = []
    for item in retrieval_results:
        uri = item.get("location", {}).get("s3Location", {}).get("uri", "")
        try:
            key, category = _parse_s3_uri(uri)
        except Exception:
            logger.warning("Skipping result with unparseable S3 URI: %s", uri)
            continue

        results.append(
            {
                "source_uri": uri,
                "document_key": key,
                "category": category,
                "text": item.get("content", {}).get("text", ""),
                "score": item.get("score", 0.0),
            }
        )

    return {"results": results, "count": len(results)}


# ---------------------------------------------------------------------------
# Server entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
