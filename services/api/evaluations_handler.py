# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Evaluations API Gateway Lambda handler — read-only evaluation metric endpoints."""

from __future__ import annotations

import json
import logging
import os
import re
from decimal import Decimal
from typing import Any

import boto3

DEFAULT_TABLE_NAME = "BushRangerEvaluations"
DEFAULT_GSI_NAME = "evaluator-timestamp-index"

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ.get("TABLE_NAME", DEFAULT_TABLE_NAME)
GSI_NAME = os.environ.get("GSI_NAME", DEFAULT_GSI_NAME)
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")

ALLOWED_PARAMS = {"start_date", "end_date", "limit"}
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DEFAULT_LIMIT = 20

# Known evaluator names used for summary queries
EVALUATOR_NAMES = [
    "Builtin.Helpfulness",
    "Builtin.ToolSelectionAccuracy",
    "BushRangerDomainRules",
]

dynamodb = boto3.resource("dynamodb")


def _cors_headers() -> dict[str, str]:
    """Return standard CORS response headers."""
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": CORS_ORIGIN,
        "Access-Control-Allow-Headers": "Authorization,Content-Type",
        "Access-Control-Allow-Methods": "GET,OPTIONS",
    }


class _DecimalEncoder(json.JSONEncoder):
    """Handle Decimal values from DynamoDB."""

    def default(self, o: object) -> Any:
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


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
        "body": json.dumps(body, cls=_DecimalEncoder),
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
            "limit": DEFAULT_LIMIT,
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

    # Parse limit
    limit = DEFAULT_LIMIT
    limit_raw = query_params.get("limit")
    if limit_raw is not None:
        try:
            limit = int(limit_raw)
            if limit < 1:
                return {}, "Parameter 'limit' must be a positive integer."
        except ValueError:
            return {}, "Parameter 'limit' must be a positive integer."

    filters: dict[str, Any] = {
        "start_date": start_date,
        "end_date": end_date,
        "limit": limit,
    }
    return filters, None


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


def _handle_summary(
    filters: dict[str, Any],
    table: Any | None = None,
) -> dict[str, Any]:
    """Handle GET /evaluations/summary.

    Queries the evaluator-timestamp-index GSI for each known evaluator
    within the requested time range, then computes the average score and
    count per evaluator.

    Args:
        filters: Parsed and validated filter parameters.
        table: Optional DynamoDB Table resource (for testability).

    Returns:
        API Gateway proxy response with EvaluationSummary[] data.
    """
    from boto3.dynamodb.conditions import Key

    if table is None:
        table = dynamodb.Table(TABLE_NAME)

    start_date = filters.get("start_date")
    end_date = filters.get("end_date")

    data: list[dict[str, Any]] = []

    for evaluator_name in EVALUATOR_NAMES:
        # Build key condition: partition key is evaluator_name
        key_condition: Any = Key("evaluator_name").eq(evaluator_name)

        # Apply optional time range on the sort key (timestamp)
        if start_date and end_date:
            key_condition = key_condition & Key("timestamp").between(start_date, end_date)
        elif start_date:
            key_condition = key_condition & Key("timestamp").gte(start_date)
        elif end_date:
            key_condition = key_condition & Key("timestamp").lte(end_date)

        query_kwargs: dict[str, Any] = {
            "IndexName": GSI_NAME,
            "KeyConditionExpression": key_condition,
        }

        # Paginate through all results for this evaluator
        items: list[dict[str, Any]] = []
        response = table.query(**query_kwargs)
        items.extend(response.get("Items", []))
        while "LastEvaluatedKey" in response:
            query_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            response = table.query(**query_kwargs)
            items.extend(response.get("Items", []))

        if not items:
            continue

        total_score = sum(float(item.get("score", 0)) for item in items)
        count = len(items)
        average_score = round(total_score / count, 4)

        data.append(
            {
                "evaluator_name": evaluator_name,
                "average_score": average_score,
                "count": count,
            }
        )

    return _success_response(data, filters)


def _handle_recent(
    filters: dict[str, Any],
    table: Any | None = None,
) -> dict[str, Any]:
    """Handle GET /evaluations/recent.

    Scans the evaluations table for recent results, sorted by timestamp
    descending, with a configurable limit.

    Args:
        filters: Parsed and validated filter parameters.
        table: Optional DynamoDB Table resource (for testability).

    Returns:
        API Gateway proxy response with EvaluationResult[] data.
    """
    from boto3.dynamodb.conditions import Attr

    if table is None:
        table = dynamodb.Table(TABLE_NAME)

    limit = filters.get("limit", DEFAULT_LIMIT)
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")

    # Build optional filter expression
    filter_parts: list[Any] = []

    # Exclude the poller state control record
    filter_parts.append(Attr("invocation_id").ne("_POLLER_STATE"))

    if start_date and end_date:
        filter_parts.append(Attr("timestamp").between(start_date, end_date))
    elif start_date:
        filter_parts.append(Attr("timestamp").gte(start_date))
    elif end_date:
        filter_parts.append(Attr("timestamp").lte(end_date))

    scan_kwargs: dict[str, Any] = {}
    if filter_parts:
        combined = filter_parts[0]
        for part in filter_parts[1:]:
            combined = combined & part
        scan_kwargs["FilterExpression"] = combined

    # Scan with pagination to collect all matching items
    all_items: list[dict[str, Any]] = []
    response = table.scan(**scan_kwargs)
    all_items.extend(response.get("Items", []))
    while "LastEvaluatedKey" in response:
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        response = table.scan(**scan_kwargs)
        all_items.extend(response.get("Items", []))

    # Sort by timestamp descending and apply limit
    all_items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    limited_items = all_items[:limit]

    # Project to response shape
    data: list[dict[str, Any]] = [
        {
            "invocation_id": item.get("invocation_id", ""),
            "evaluator_name": item.get("evaluator_name", ""),
            "score": float(item.get("score", 0)),
            "rationale": item.get("rationale", ""),
            "prompt_summary": item.get("prompt_summary", ""),
            "timestamp": item.get("timestamp", ""),
        }
        for item in limited_items
    ]

    return _success_response(data, filters)


# ---------------------------------------------------------------------------
# Lambda entry-point
# ---------------------------------------------------------------------------

# Route map: path -> handler function
_ROUTES: dict[str, Any] = {
    "/evaluations/summary": _handle_summary,
    "/evaluations/recent": _handle_recent,
}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """API Gateway Lambda proxy handler for evaluations endpoints.

    Routes GET requests to the appropriate handler based on the request
    path. Parses and validates query parameters before dispatching.

    Args:
        event: API Gateway proxy integration event.
        context: Lambda context object.

    Returns:
        API Gateway proxy response dict.
    """
    # Support both API Gateway v1 (path/httpMethod) and v2 (rawPath/requestContext)
    http_method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "")
    path = event.get("rawPath") or event.get("path", "")

    logger.info("evaluations event path=%s method=%s", path, http_method)

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
