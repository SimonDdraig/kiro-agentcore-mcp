# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Shared model for the BushRangers DynamoDB table."""

from dataclasses import dataclass

TABLE_NAME = "BushRangers"
PARTITION_KEY = "ranger_id"


@dataclass
class RangerRecord:
    """A ranger profile record stored in DynamoDB."""

    ranger_id: str
    name: str
    email: str
    region: str
    phone: str
    active: bool
    start_date: str  # ISO-8601 date
