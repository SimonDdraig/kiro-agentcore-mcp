# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Wildlife Sightings MCP server — DynamoDB-backed tools for wildlife sighting CRUD."""

from __future__ import annotations

import hashlib
import math
import os
import uuid
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr, Key
from mcp.server.fastmcp import FastMCP

from models.sightings import (
    GSI_NAME,
    PARTITION_KEY,
    SORT_KEY,
    TABLE_NAME,
)

# ---------------------------------------------------------------------------
# MCP server instance
# ---------------------------------------------------------------------------
mcp = FastMCP("wildlife-sightings")

# ---------------------------------------------------------------------------
# DynamoDB helpers
# ---------------------------------------------------------------------------
_TABLE_NAME_OVERRIDE = os.environ.get("DYNAMODB_TABLE_NAME", TABLE_NAME)


def _get_table() -> Any:
    """Return a DynamoDB Table resource."""
    dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return dynamodb.Table(_TABLE_NAME_OVERRIDE)


def _make_sort_key(date_iso: str, latitude: float, longitude: float) -> str:
    """Build the composite sort key: ISO-date + location hash."""
    loc_hash = hashlib.md5(f"{latitude},{longitude}".encode(), usedforsecurity=False).hexdigest()[:8]
    return f"{date_iso}#{loc_hash}"


def _record_to_dict(item: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw DynamoDB item into a friendly sighting dict."""
    return {
        "sighting_id": item.get("sighting_id", ""),
        "species": item.get(PARTITION_KEY, ""),
        "latitude": float(item.get("latitude", 0)),
        "longitude": float(item.get("longitude", 0)),
        "date": item.get("date", ""),
        "conservation_status": item.get("conservation_status", ""),
        "observer_notes": item.get("observer_notes", ""),
    }


# ---------------------------------------------------------------------------
# Validation helpers (Req 1.6)
# ---------------------------------------------------------------------------


def _validate_required_fields(
    species: str | None,
    latitude: float | None,
    longitude: float | None,
    date: str | None,
) -> dict[str, Any] | None:
    """Return a structured error dict if any required field is missing/empty, else None."""
    missing: list[str] = []
    if not species:
        missing.append("species")
    if latitude is None:
        missing.append("latitude")
    if longitude is None:
        missing.append("longitude")
    if not date:
        missing.append("date")

    if missing:
        return {
            "error": "validation_error",
            "message": f"Missing required fields: {', '.join(missing)}",
            "missing_fields": missing,
        }
    return None


# ---------------------------------------------------------------------------
# Haversine distance (km)
# ---------------------------------------------------------------------------

_EARTH_RADIUS_KM = 6371.0


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in km between two lat/lng points."""
    lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
    lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    return _EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def create_sighting(
    species: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    date: str | None = None,
    conservation_status: str = "least_concern",
    observer_notes: str = "",
) -> dict[str, Any]:
    """Record a new wildlife sighting.

    Args:
        species: Species name (required).
        latitude: Latitude of the sighting location (required).
        longitude: Longitude of the sighting location (required).
        date: ISO-8601 date string, e.g. '2025-06-15' (required).
        conservation_status: IUCN status — one of critically_endangered,
            endangered, vulnerable, near_threatened, least_concern.
        observer_notes: Free-text notes from the observer.

    Returns:
        The created sighting record with a generated unique ID, or a
        structured error if required fields are missing.
    """
    # --- Validate required fields (Req 1.6) ---
    validation_err = _validate_required_fields(species, latitude, longitude, date)
    if validation_err is not None:
        return validation_err

    # At this point the type-checker knows these are non-None, but let's
    # narrow for safety and to satisfy mypy.
    if species is None or latitude is None or longitude is None or date is None:
        msg = "Required fields must not be None after validation"
        raise ValueError(msg)

    sighting_id = str(uuid.uuid4())
    sort_key = _make_sort_key(date, latitude, longitude)

    item: dict[str, Any] = {
        PARTITION_KEY: species,
        SORT_KEY: sort_key,
        "sighting_id": sighting_id,
        "latitude": str(latitude),
        "longitude": str(longitude),
        "date": date,
        "conservation_status": conservation_status,
        "observer_notes": observer_notes,
    }

    table = _get_table()
    table.put_item(Item=item)

    return {
        "sighting_id": sighting_id,
        "species": species,
        "latitude": latitude,
        "longitude": longitude,
        "date": date,
        "conservation_status": conservation_status,
        "observer_notes": observer_notes,
    }


@mcp.tool()
def query_by_species(
    species: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Find sightings for a given species, optionally within a date range.

    Args:
        species: Species name to query (partition key).
        start_date: Optional ISO-8601 start date (inclusive).
        end_date: Optional ISO-8601 end date (inclusive).

    Returns:
        A dict with a 'sightings' list of matching records.
    """
    table = _get_table()

    key_condition: Any = Key(PARTITION_KEY).eq(species)

    # The sort key is "date#lochash", so we can do begins_with / between
    # on the date prefix for range filtering.
    if start_date and end_date:
        key_condition = key_condition & Key(SORT_KEY).between(start_date, end_date + "~")
    elif start_date:
        key_condition = key_condition & Key(SORT_KEY).gte(start_date)
    elif end_date:
        key_condition = key_condition & Key(SORT_KEY).lte(end_date + "~")

    response = table.query(KeyConditionExpression=key_condition)
    items = [_record_to_dict(i) for i in response.get("Items", [])]
    return {"sightings": items, "count": len(items)}


@mcp.tool()
def query_by_location(
    latitude: float,
    longitude: float,
    radius_km: float,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Find sightings within a geographic radius of a point.

    Uses a DynamoDB scan with haversine post-filtering (acceptable for
    ranger-scale data volumes).

    Args:
        latitude: Centre latitude.
        longitude: Centre longitude.
        radius_km: Search radius in kilometres.
        start_date: Optional ISO-8601 start date filter.
        end_date: Optional ISO-8601 end date filter.

    Returns:
        A dict with a 'sightings' list of matching records.
    """
    table = _get_table()

    filter_expr: Any = None
    if start_date and end_date:
        filter_expr = Attr("date").between(start_date, end_date)
    elif start_date:
        filter_expr = Attr("date").gte(start_date)
    elif end_date:
        filter_expr = Attr("date").lte(end_date)

    scan_kwargs: dict[str, Any] = {}
    if filter_expr is not None:
        scan_kwargs["FilterExpression"] = filter_expr

    response = table.scan(**scan_kwargs)
    all_items = response.get("Items", [])

    # Paginate through all results
    while "LastEvaluatedKey" in response:
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        response = table.scan(**scan_kwargs)
        all_items.extend(response.get("Items", []))

    # Haversine filter
    results: list[dict[str, Any]] = []
    for item in all_items:
        item_lat = float(item.get("latitude", 0))
        item_lng = float(item.get("longitude", 0))
        dist = _haversine(latitude, longitude, item_lat, item_lng)
        if dist <= radius_km:
            record = _record_to_dict(item)
            record["distance_km"] = round(dist, 2)
            results.append(record)

    return {"sightings": results, "count": len(results)}


@mcp.tool()
def query_by_status(
    conservation_status: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Find sightings by conservation status using the GSI.

    Args:
        conservation_status: IUCN status to filter by (e.g. 'endangered').
        start_date: Optional ISO-8601 start date (inclusive).
        end_date: Optional ISO-8601 end date (inclusive).

    Returns:
        A dict with a 'sightings' list of matching records.
    """
    table = _get_table()

    key_condition: Any = Key("conservation_status").eq(conservation_status)

    if start_date and end_date:
        key_condition = key_condition & Key("date").between(start_date, end_date)
    elif start_date:
        key_condition = key_condition & Key("date").gte(start_date)
    elif end_date:
        key_condition = key_condition & Key("date").lte(end_date)

    response = table.query(
        IndexName=GSI_NAME,
        KeyConditionExpression=key_condition,
    )
    items = [_record_to_dict(i) for i in response.get("Items", [])]
    return {"sightings": items, "count": len(items)}


# ---------------------------------------------------------------------------
# Server entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
