// Copyright 2025 Bush Ranger AI Project. All rights reserved.

import type { EvaluationSummary, EvaluationResult, EvaluationsResponse } from './evaluationTypes';

const API_ENDPOINT = import.meta.env.VITE_API_ENDPOINT ?? '';
const REQUEST_TIMEOUT_MS = 30_000;

/**
 * Generic fetch helper that calls an evaluations endpoint,
 * enforces a timeout, and unwraps the response envelope.
 */
async function fetchEvaluations<T>(
  path: string,
  params: URLSearchParams,
  accessToken: string | null,
): Promise<EvaluationsResponse<T>> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const qs = params.toString();
    const url = `${API_ENDPOINT}${path}${qs ? `?${qs}` : ''}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      signal: controller.signal,
    });

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(
        (body as { error?: string }).error ?? `Request failed with status ${response.status}`,
      );
    }

    return (await response.json()) as EvaluationsResponse<T>;
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('Request timed out. Please try again.');
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

/** Fetch average scores per evaluator over a date range. */
export async function fetchEvaluationSummary(
  startDate: string,
  endDate: string,
  accessToken: string | null,
): Promise<EvaluationsResponse<EvaluationSummary>> {
  const params = new URLSearchParams();
  if (startDate) {
    params.set('start_date', startDate);
  }
  if (endDate) {
    params.set('end_date', endDate);
  }
  return fetchEvaluations<EvaluationSummary>('/evaluations/summary', params, accessToken);
}

/** Fetch the most recent evaluation results. */
export async function fetchRecentEvaluations(
  limit: number = 20,
  accessToken: string | null = null,
): Promise<EvaluationsResponse<EvaluationResult>> {
  const params = new URLSearchParams();
  if (limit !== 20) {
    params.set('limit', String(limit));
  }
  return fetchEvaluations<EvaluationResult>('/evaluations/recent', params, accessToken);
}
