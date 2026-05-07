// Copyright 2025 Bush Ranger AI Project. All rights reserved.

/** Average score summary for a single evaluator over a time range. */
export interface EvaluationSummary {
  evaluator_name: string;
  average_score: number;
  count: number;
}

/** A single evaluation result record from the Evaluations table. */
export interface EvaluationResult {
  invocation_id: string;
  evaluator_name: string;
  score: number;
  rationale: string;
  prompt_summary: string;
  timestamp: string;
}

/** A single data point for the evaluation trend chart. */
export interface EvaluationTrendPoint {
  date: string; // YYYY-MM-DD
  evaluator_name: string;
  average_score: number;
  count: number;
}

/** Consistent JSON envelope returned by all evaluations endpoints. */
export interface EvaluationsResponse<T> {
  data: T[];
  count: number;
  filters_applied: {
    start_date: string;
    end_date: string;
  };
}
