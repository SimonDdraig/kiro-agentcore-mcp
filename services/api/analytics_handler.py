# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Analytics API Gateway Lambda handler — read-only sighting aggregation endpoints."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ.get("TABLE_NAME", "BushRangerSightings")
GSI_NAME = os.environ.get("GSI_NAME", "conservation_status-date-index")
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")

ALLOWED_PARAMS = {"start_date", "end_date", "species", "conservation_status"}
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

dynamodb = boto3.resource("dynamodb")


def _cors_headers() -> dict[str, str]:
    """Return standard CORS response headers."""
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": CORS_ORIGIN,
        "Access-Control-Allow-Headers": "Authorization,Content-Type",
        "Access-Control-Allow-Methods": "GET,OPTIONS",
    }


def _success_response(
    data: list[dict[str, Any]],
    filters_applied: dict[str, Any],
) -> dict[str, Any]:
    """Build a consistent success response envelope.

    Args:
        data: The aggregated result list.
        filters_applied: The filters that were applied to produce the result.

    Returns:
        API Gateway proxy response with 200 status.
    """
    body = {
        "data": data,
        "count": len(data),
        "filters_applied": filters_applied,
    }
    return {
        "statusCode": 200,
        "headers": _cors_headers(),
        "body": json.dumps(body),
    }


def _error_response(status_code: int, message: str) -> dict[str, Any]:
    """Build a consistent error response.

    Args:
        status_code: HTTP status code.
        message: Human-readable error description.

    Returns:
        API Gateway proxy response with the given status code.
    """
    return {
        "statusCode": status_code,
        "headers": _cors_headers(),
        "body": json.dumps({"error": message}),
    }


def _parse_filters(
    query_params: dict[str, str] | None,
) -> tuple[dict[str, Any], str | None]:
    """Parse and validate query parameters from the API Gateway event.

    Args:
        query_params: Raw query string parameters from the event.

    Returns:
        A tuple of (parsed_filters dict, error_message or None).
        If error_message is not None the request should be rejected with 400.
    """
    if not query_params:
        return {
            "start_date": None,
            "end_date": None,
            "species": [],
            "conservation_status": [],
        }, None

    # Reject unknown parameters
    unknown = set(query_params.keys()) - ALLOWED_PARAMS
    if unknown:
        return {}, f"Unknown parameter: {sorted(unknown)[0]}"

    start_date = query_params.get("start_date")
    end_date = query_params.get("end_date")

    # Validate date formats
    if start_date and not DATE_PATTERN.match(start_date):
        return {}, "Invalid date format for 'start_date'. Use ISO-8601 (YYYY-MM-DD)."
    if end_date and not DATE_PATTERN.match(end_date):
        return {}, "Invalid date format for 'end_date'. Use ISO-8601 (YYYY-MM-DD)."

    # Parse comma-separated list params
    species_raw = query_params.get("species", "")
    species_list = [s.strip() for s in species_raw.split(",") if s.strip()] if species_raw else []

    status_raw = query_params.get("conservation_status", "")
    status_list = [s.strip() for s in status_raw.split(",") if s.strip()] if status_raw else []

    filters: dict[str, Any] = {
        "start_date": start_date,
        "end_date": end_date,
        "species": species_list,
        "conservation_status": status_list,
    }
    return filters, None


# ---------------------------------------------------------------------------
# Known park locations — (rounded_lat, rounded_lng) -> name
# Matches the 20 locations from the seed script. Coordinates are rounded
# to integers so that jittered sighting coordinates (±0.5°) map back to
# the correct park name.
# ---------------------------------------------------------------------------
_KNOWN_LOCATIONS: dict[tuple[int, int], str] = {
    (-34, 150): "Blue Mountains NP, NSW",
    (-13, 133): "Kakadu NP, NT",
    (-16, 145): "Daintree Rainforest, QLD",
    (-39, 144): "Great Otway NP, VIC",
    (-42, 146): "Cradle Mountain, TAS",
    (-36, 137): "Kangaroo Island, SA",
    (-23, 114): "Ningaloo Reef, WA",
    (-25, 131): "Uluru-Kata Tjuta NP, NT",
    (-39, 146): "Wilsons Promontory, VIC",
    (-28, 153): "Lamington NP, QLD",
    (-34, 151): "Ku-ring-gai Chase NP, NSW",
    (-42, 148): "Freycinet NP, TAS",
    (-31, 139): "Flinders Ranges, SA",
    (-13, 131): "Litchfield NP, NT",
    (-26, 153): "Noosa NP, QLD",
    (-37, 142): "Grampians NP, VIC",
    (-34, 118): "Stirling Range NP, WA",
    (-35, 151): "Jervis Bay, NSW",
    (-32, 116): "Rottnest Island, WA",
}


def _derive_location_name(rounded_lat: int, rounded_lng: int) -> str:
    """Derive a human-readable park name from rounded coordinates.

    Falls back to a generic lat/lng label if the coordinates don't match
    any known park location.
    """
    return _KNOWN_LOCATIONS.get(
        (rounded_lat, rounded_lng),
        f"Location ({rounded_lat}, {rounded_lng})",
    )


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


def _handle_locations(filters: dict[str, Any]) -> dict[str, Any]:
    """Handle GET /analytics/locations.

    Scans the sightings table with optional date/species/status filters,
    groups results by rounded lat/lng to cluster nearby sightings, and
    derives a human-readable location name from a known park mapping.

    Args:
        filters: Parsed and validated filter parameters.

    Returns:
        API Gateway proxy response with LocationData[] aggregation.
    """
    from boto3.dynamodb.conditions import Attr

    table = dynamodb.Table(TABLE_NAME)

    # Build optional FilterExpression
    filter_parts: list[Any] = []
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    species_list: list[str] = filters.get("species", [])
    status_list: list[str] = filters.get("conservation_status", [])

    if start_date and end_date:
        filter_parts.append(Attr("date").between(start_date, end_date))
    elif start_date:
        filter_parts.append(Attr("date").gte(start_date))
    elif end_date:
        filter_parts.append(Attr("date").lte(end_date))

    if species_list:
        filter_parts.append(Attr("species").is_in(species_list))

    if status_list:
        filter_parts.append(Attr("conservation_status").is_in(status_list))

    scan_kwargs: dict[str, Any] = {}
    if filter_parts:
        combined = filter_parts[0]
        for part in filter_parts[1:]:
            combined = combined & part
        scan_kwargs["FilterExpression"] = combined

    # Scan with pagination
    all_items: list[dict[str, Any]] = []
    response = table.scan(**scan_kwargs)
    all_items.extend(response.get("Items", []))
    while "LastEvaluatedKey" in response:
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        response = table.scan(**scan_kwargs)
        all_items.extend(response.get("Items", []))

    # Group by rounded lat/lng (integer rounding clusters ±0.5 jitter)
    location_counts: dict[tuple[int, int], dict[str, Any]] = {}
    for item in all_items:
        lat = float(item.get("latitude", 0))
        lng = float(item.get("longitude", 0))
        key = (round(lat), round(lng))
        if key not in location_counts:
            location_counts[key] = {"lat_sum": 0.0, "lng_sum": 0.0, "count": 0}
        location_counts[key]["lat_sum"] += lat
        location_counts[key]["lng_sum"] += lng
        location_counts[key]["count"] += 1

    # Build response with average coordinates and derived location names
    data: list[dict[str, Any]] = []
    for (rlat, rlng), info in location_counts.items():
        count = info["count"]
        avg_lat = info["lat_sum"] / count
        avg_lng = info["lng_sum"] / count
        data.append(
            {
                "latitude": round(avg_lat, 4),
                "longitude": round(avg_lng, 4),
                "locationName": _derive_location_name(rlat, rlng),
                "count": count,
            }
        )

    return _success_response(data, filters)


def _handle_trends(filters: dict[str, Any]) -> dict[str, Any]:
    """Handle GET /analytics/trends.

    Queries or scans the sightings table, groups results by species and
    month (YYYY-MM), and returns TrendData[].  When a species filter is
    provided, uses Query on the partition key for each species (more
    efficient).  When no species filter is given, scans the full table
    and returns aggregated totals with species="All".

    Args:
        filters: Parsed and validated filter parameters.

    Returns:
        API Gateway proxy response with TrendData[] aggregation.
    """
    from boto3.dynamodb.conditions import Attr, Key

    table = dynamodb.Table(TABLE_NAME)

    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    species_list: list[str] = filters.get("species", [])
    status_list: list[str] = filters.get("conservation_status", [])

    all_items: list[dict[str, Any]] = []

    if species_list:
        # Query by partition key for each requested species
        for sp in species_list:
            query_kwargs: dict[str, Any] = {
                "KeyConditionExpression": Key("species").eq(sp),
            }

            # Build FilterExpression for non-key attributes
            filter_parts: list[Any] = []
            if start_date and end_date:
                filter_parts.append(Attr("date").between(start_date, end_date))
            elif start_date:
                filter_parts.append(Attr("date").gte(start_date))
            elif end_date:
                filter_parts.append(Attr("date").lte(end_date))

            if status_list:
                filter_parts.append(Attr("conservation_status").is_in(status_list))

            if filter_parts:
                combined = filter_parts[0]
                for part in filter_parts[1:]:
                    combined = combined & part
                query_kwargs["FilterExpression"] = combined

            response = table.query(**query_kwargs)
            all_items.extend(response.get("Items", []))
            while "LastEvaluatedKey" in response:
                query_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
                response = table.query(**query_kwargs)
                all_items.extend(response.get("Items", []))
    else:
        # No species filter — scan the full table
        scan_kwargs: dict[str, Any] = {}
        filter_parts = []

        if start_date and end_date:
            filter_parts.append(Attr("date").between(start_date, end_date))
        elif start_date:
            filter_parts.append(Attr("date").gte(start_date))
        elif end_date:
            filter_parts.append(Attr("date").lte(end_date))

        if status_list:
            filter_parts.append(Attr("conservation_status").is_in(status_list))

        if filter_parts:
            combined = filter_parts[0]
            for part in filter_parts[1:]:
                combined = combined & part
            scan_kwargs["FilterExpression"] = combined

        response = table.scan(**scan_kwargs)
        all_items.extend(response.get("Items", []))
        while "LastEvaluatedKey" in response:
            scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            response = table.scan(**scan_kwargs)
            all_items.extend(response.get("Items", []))

    # Group by (species, month) and count
    trend_counts: dict[tuple[str, str], int] = {}
    for item in all_items:
        sp = item.get("species", "Unknown")
        date_str = item.get("date", "")
        month = date_str[:7] if len(date_str) >= 7 else "Unknown"
        key = (sp, month)
        trend_counts[key] = trend_counts.get(key, 0) + 1

    # Build response data
    if species_list:
        # Return per-species trend lines
        data: list[dict[str, Any]] = [
            {"month": month, "species": sp, "count": count} for (sp, month), count in sorted(trend_counts.items())
        ]
    else:
        # Aggregate totals across all species — single "All" line
        month_totals: dict[str, int] = {}
        for (_, month), count in trend_counts.items():
            month_totals[month] = month_totals.get(month, 0) + count
        data = [{"month": month, "species": "All", "count": count} for month, count in sorted(month_totals.items())]

    return _success_response(data, filters)


def _handle_status(filters: dict[str, Any]) -> dict[str, Any]:
    """Handle GET /analytics/status.

    Queries the conservation_status-date-index GSI for each requested
    IUCN status, applies optional date range via KeyConditionExpression
    and optional species post-filter, then groups results by status with
    sighting counts and distinct species lists.

    Args:
        filters: Parsed and validated filter parameters.

    Returns:
        API Gateway proxy response with StatusData[] aggregation.
    """
    from boto3.dynamodb.conditions import Attr, Key

    table = dynamodb.Table(TABLE_NAME)

    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    species_list: list[str] = filters.get("species", [])
    status_list: list[str] = filters.get("conservation_status", [])

    all_statuses = [
        "critically_endangered",
        "endangered",
        "vulnerable",
        "near_threatened",
        "least_concern",
    ]

    statuses_to_query = status_list if status_list else all_statuses

    # Collect all matching items across all queried statuses
    all_items: list[dict[str, Any]] = []

    for status in statuses_to_query:
        # Build KeyConditionExpression: partition key + optional date range
        key_condition: Any = Key("conservation_status").eq(status)
        if start_date and end_date:
            key_condition = key_condition & Key("date").between(start_date, end_date)
        elif start_date:
            key_condition = key_condition & Key("date").gte(start_date)
        elif end_date:
            key_condition = key_condition & Key("date").lte(end_date)

        query_kwargs: dict[str, Any] = {
            "IndexName": GSI_NAME,
            "KeyConditionExpression": key_condition,
        }

        # Post-filter by species if provided
        if species_list:
            query_kwargs["FilterExpression"] = Attr("species").is_in(species_list)

        response = table.query(**query_kwargs)
        all_items.extend(response.get("Items", []))
        while "LastEvaluatedKey" in response:
            query_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            response = table.query(**query_kwargs)
            all_items.extend(response.get("Items", []))

    # Group by conservation_status: count + distinct species
    status_agg: dict[str, dict[str, Any]] = {}
    for item in all_items:
        cs = item.get("conservation_status", "unknown")
        if cs not in status_agg:
            status_agg[cs] = {"count": 0, "species_set": set()}
        status_agg[cs]["count"] += 1
        sp = item.get("species")
        if sp:
            status_agg[cs]["species_set"].add(sp)

    data: list[dict[str, Any]] = [
        {
            "conservation_status": cs,
            "count": info["count"],
            "species": sorted(info["species_set"]),
        }
        for cs, info in sorted(status_agg.items())
    ]

    return _success_response(data, filters)


# ---------------------------------------------------------------------------
# Lambda entry-point
# ---------------------------------------------------------------------------

# Route map: path -> handler function
_ROUTES: dict[str, Any] = {
    "/analytics/locations": _handle_locations,
    "/analytics/trends": _handle_trends,
    "/analytics/status": _handle_status,
}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """API Gateway Lambda proxy handler for analytics endpoints.

    Routes GET requests to the appropriate aggregation handler based on
    the request path. Parses and validates query parameters before
    dispatching.

    Args:
        event: API Gateway proxy integration event.
        context: Lambda context object.

    Returns:
        API Gateway proxy response dict.
    """
    # Support both API Gateway v1 (path/httpMethod) and v2 (rawPath/requestContext)
    http_method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "")
    path = event.get("rawPath") or event.get("path", "")

    logger.info("analytics event path=%s method=%s", path, http_method)

    # Handle CORS preflight
    if http_method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": _cors_headers(),
            "body": "",
        }

    route_handler = _ROUTES.get(path)
    if route_handler is None:
        return _error_response(404, f"Not found: {path}")

    # Parse and validate query parameters
    query_params = event.get("queryStringParameters") or {}
    filters, error = _parse_filters(query_params)
    if error:
        return _error_response(400, error)

    try:
        result: dict[str, Any] = route_handler(filters)
        return result
    except Exception:
        logger.exception("Error handling %s", path)
        return _error_response(500, "Internal server error")
