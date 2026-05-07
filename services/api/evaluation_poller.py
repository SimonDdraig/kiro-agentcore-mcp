# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Poller Lambda — reads evaluation results from CloudWatch Logs and writes to DynamoDB.

Triggered by an EventBridge rule every 1 minute. Reads new evaluation result
log events from the CloudWatch results log group and batch-writes them to the
Evaluations DynamoDB table.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import UTC, datetime
from typing import Any

import boto3

TABLE_NAME = "BushRangerEvaluations"
PARTITION_KEY = "invocation_id"
SORT_KEY = "evaluator_ts"

logger = logging.getLogger()
logger.setLevel(logging.INFO)

EVALUATIONS_TABLE_NAME = os.environ.get("EVALUATIONS_TABLE_NAME", TABLE_NAME)
RESULTS_LOG_GROUP = os.environ.get("RESULTS_LOG_GROUP", "")

# Poller state control record keys
POLLER_STATE_PK = "_POLLER_STATE"
POLLER_STATE_SK = "_CONTROL"

# TTL: 30 days in seconds
TTL_SECONDS = 30 * 24 * 60 * 60

# DynamoDB batch write limit
BATCH_WRITE_MAX = 25

dynamodb = boto3.resource("dynamodb")
logs_client = boto3.client("logs")


def parse_evaluation_event(log_event: dict[str, Any]) -> dict[str, Any] | None:
    """Parse a single CloudWatch log event into an EvaluationResult dict.

    This is a standalone, testable function. It takes a raw log event dict
    (as returned by CloudWatch Logs Insights) and extracts the fields needed
    for a DynamoDB EvaluationResult item.

    Args:
        log_event: A dict representing a single CloudWatch log event.
            Expected to contain a JSON-encoded ``@message`` field (or a
            ``message`` field) with evaluation result data including:
            ``evaluator_name``, ``score``, ``rationale``, ``trace_id``,
            ``session_id``, and ``prompt_summary``.

    Returns:
        A dict with all EvaluationResult attributes ready for DynamoDB,
        or ``None`` if the event is malformed or missing required fields.
    """
    try:
        # CloudWatch Logs Insights returns results with @message or message
        raw_message = log_event.get("@message") or log_event.get("message")
        if raw_message is None:
            logger.warning("Log event missing @message/message field: %s", log_event)
            return None

        # Parse the JSON message body
        if isinstance(raw_message, str):
            body = json.loads(raw_message)
        elif isinstance(raw_message, dict):
            body = raw_message
        else:
            logger.warning("Unexpected message type %s: %s", type(raw_message).__name__, log_event)
            return None

        # Extract required fields
        evaluator_name = body.get("evaluator_name")
        score = body.get("score")
        trace_id = body.get("trace_id")

        if evaluator_name is None or score is None or trace_id is None:
            logger.warning("Log event missing required fields (evaluator_name, score, trace_id): %s", body)
            return None

        # Validate score is numeric and in range
        try:
            score_float = float(score)
        except (TypeError, ValueError):
            logger.warning("Invalid score value '%s' in log event: %s", score, body)
            return None

        if not (0.0 <= score_float <= 1.0):
            logger.warning("Score %.4f out of range [0.0, 1.0]: %s", score_float, body)
            return None

        # Extract optional fields with defaults
        rationale = str(body.get("rationale", ""))
        session_id = str(body.get("session_id", ""))
        prompt_summary = str(body.get("prompt_summary", ""))[:200]

        # Derive timestamp from the log event or body
        timestamp = (
            body.get("timestamp")
            or log_event.get("@timestamp")
            or log_event.get("timestamp")
            or datetime.now(UTC).isoformat()
        )

        # Build composite sort key: evaluator_name#timestamp
        evaluator_ts = f"{evaluator_name}#{timestamp}"

        # Compute TTL (30 days from now)
        ttl = int(time.time()) + TTL_SECONDS

        return {
            PARTITION_KEY: str(trace_id),
            SORT_KEY: evaluator_ts,
            "evaluator_name": str(evaluator_name),
            "score": score_float,
            "rationale": rationale,
            "session_id": session_id,
            "prompt_summary": prompt_summary,
            "timestamp": str(timestamp),
            "ttl": ttl,
        }

    except (json.JSONDecodeError, AttributeError) as exc:
        logger.warning("Failed to parse log event: %s — %s", exc, log_event)
        return None


def _get_last_processed_timestamp(table: Any) -> str:
    """Read the last-processed timestamp from the poller state control record.

    Args:
        table: DynamoDB Table resource for the evaluations table.

    Returns:
        ISO-8601 timestamp string, or a default epoch timestamp if no
        state record exists yet.
    """
    try:
        response = table.get_item(
            Key={
                PARTITION_KEY: POLLER_STATE_PK,
                SORT_KEY: POLLER_STATE_SK,
            }
        )
        item = response.get("Item")
        if item and "last_processed_ts" in item:
            return str(item["last_processed_ts"])
    except Exception:
        logger.exception("Failed to read poller state from DynamoDB")

    # Default: 1 hour ago (first run or error recovery)
    return "1970-01-01T00:00:00Z"


def _update_last_processed_timestamp(table: Any, timestamp: str) -> None:
    """Update the poller state control record with the latest processed timestamp.

    Args:
        table: DynamoDB Table resource for the evaluations table.
        timestamp: ISO-8601 timestamp to store.
    """
    try:
        table.put_item(
            Item={
                PARTITION_KEY: POLLER_STATE_PK,
                SORT_KEY: POLLER_STATE_SK,
                "last_processed_ts": timestamp,
            }
        )
    except Exception:
        logger.exception("Failed to update poller state in DynamoDB")


def _query_cloudwatch_results(log_group: str, start_ts: str) -> list[dict[str, Any]]:
    """Query CloudWatch Logs Insights for new evaluation result events.

    Args:
        log_group: The CloudWatch log group name for evaluation results.
        start_ts: ISO-8601 timestamp — only events after this time are returned.

    Returns:
        A list of log event dicts from the query results.
    """
    if not log_group:
        logger.warning("RESULTS_LOG_GROUP not configured, skipping CloudWatch query")
        return []

    try:
        # Parse start timestamp to epoch seconds
        try:
            start_epoch = int(datetime.fromisoformat(start_ts.replace("Z", "+00:00")).timestamp())
        except (ValueError, AttributeError):
            start_epoch = 0

        end_epoch = int(datetime.now(UTC).timestamp())

        response = logs_client.start_query(
            logGroupName=log_group,
            startTime=start_epoch,
            endTime=end_epoch,
            queryString="fields @timestamp, @message | sort @timestamp asc | limit 500",
        )
        query_id = response["queryId"]

        # Poll for query completion
        status = "Running"
        results: list[list[dict[str, str]]] = []
        while status in ("Running", "Scheduled"):
            time.sleep(0.5)
            query_response = logs_client.get_query_results(queryId=query_id)
            status = query_response["status"]
            results = query_response.get("results", [])

        if status != "Complete":
            logger.warning("CloudWatch Logs Insights query ended with status: %s", status)
            return []

        # Convert results from list-of-field-dicts to flat dicts
        events: list[dict[str, Any]] = []
        for result_row in results:
            event: dict[str, Any] = {}
            for field in result_row:
                event[field["field"]] = field["value"]
            events.append(event)

        return events

    except Exception:
        logger.exception("Failed to query CloudWatch Logs Insights")
        return []


def _batch_write_items(table: Any, items: list[dict[str, Any]]) -> None:
    """Batch-write evaluation result items to DynamoDB.

    Handles chunking into batches of 25 (DynamoDB limit) and retries
    unprocessed items.

    Args:
        table: DynamoDB Table resource for the evaluations table.
        items: List of DynamoDB item dicts to write.
    """
    if not items:
        return

    table_name = table.table_name

    for i in range(0, len(items), BATCH_WRITE_MAX):
        batch = items[i : i + BATCH_WRITE_MAX]
        request_items = {table_name: [{"PutRequest": {"Item": item}} for item in batch]}

        try:
            response = dynamodb.meta.client.batch_write_item(RequestItems=request_items)

            # Retry unprocessed items (once)
            unprocessed = response.get("UnprocessedItems", {})
            if unprocessed:
                logger.warning("Retrying %d unprocessed items", len(unprocessed.get(table_name, [])))
                dynamodb.meta.client.batch_write_item(RequestItems=unprocessed)

        except Exception:
            logger.exception("Failed to batch-write %d items to DynamoDB", len(batch))


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point — poll CloudWatch for evaluation results and write to DynamoDB.

    Triggered by EventBridge on a 1-minute schedule.

    Args:
        event: EventBridge scheduled event (ignored).
        context: Lambda context object.

    Returns:
        A summary dict with the count of processed results.
    """
    logger.info("Evaluation poller triggered")

    table = dynamodb.Table(EVALUATIONS_TABLE_NAME)
    log_group = RESULTS_LOG_GROUP

    # Step 1: Read last-processed timestamp
    last_ts = _get_last_processed_timestamp(table)
    logger.info("Last processed timestamp: %s", last_ts)

    # Step 2: Query CloudWatch for new events
    raw_events = _query_cloudwatch_results(log_group, last_ts)
    logger.info("Retrieved %d raw events from CloudWatch", len(raw_events))

    if not raw_events:
        return {"statusCode": 200, "processed": 0, "message": "No new events"}

    # Step 3: Parse events into DynamoDB items
    items: list[dict[str, Any]] = []
    latest_ts = last_ts
    skipped = 0

    for raw_event in raw_events:
        parsed = parse_evaluation_event(raw_event)
        if parsed is None:
            skipped += 1
            continue

        items.append(parsed)

        # Track the latest timestamp for the control record
        event_ts = parsed.get("timestamp", "")
        if event_ts > latest_ts:
            latest_ts = event_ts

    logger.info("Parsed %d items (%d skipped)", len(items), skipped)

    # Step 4: Batch-write to DynamoDB
    _batch_write_items(table, items)

    # Step 5: Update the control record with the latest timestamp
    if items and latest_ts > last_ts:
        _update_last_processed_timestamp(table, latest_ts)
        logger.info("Updated poller state to %s", latest_ts)

    return {
        "statusCode": 200,
        "processed": len(items),
        "skipped": skipped,
        "latest_timestamp": latest_ts,
    }
