# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""Shared model for the Evaluations DynamoDB table."""

from dataclasses import dataclass

TABLE_NAME = "BushRangerEvaluations"
PARTITION_KEY = "invocation_id"
SORT_KEY = "evaluator_ts"
GSI_NAME = "evaluator-timestamp-index"


@dataclass
class EvaluationResult:
    """An evaluation result record stored in DynamoDB."""

    invocation_id: str
    evaluator_ts: str
    evaluator_name: str
    score: float
    rationale: str
    session_id: str
    prompt_summary: str
    timestamp: str
    ttl: int
