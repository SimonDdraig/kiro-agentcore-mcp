# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Shared model for the Conservation Documents S3 bucket."""

from dataclasses import dataclass

DOCS_BUCKET_PREFIX = "bush-ranger-docs"
CATEGORIES = ("species", "management_plans", "emergency")


@dataclass
class DocumentMetadata:
    """Metadata for a conservation document in S3."""

    key: str
    title: str
    category: str
