# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Shared model for the Wildlife Sightings DynamoDB table."""

from dataclasses import dataclass
from datetime import datetime

TABLE_NAME = "BushRangerSightings"
PARTITION_KEY = "species"
SORT_KEY = "date_location"
GSI_NAME = "conservation_status-date-index"


@dataclass
class SightingRecord:
    """A wildlife sighting record stored in DynamoDB."""

    species: str
    latitude: float
    longitude: float
    date: datetime
    conservation_status: str
    observer_notes: str
    sighting_id: str | None = None
