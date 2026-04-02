// Copyright 2025 Bush Ranger AI Project. All rights reserved.

import type {
  FilterState,
  LocationData,
  TrendData,
  StatusData,
  AnalyticsResponse,
} from './analyticsTypes';

const API_ENDPOINT = import.meta.env.VITE_API_ENDPOINT ?? '';
const REQUEST_TIMEOUT_MS = 30_000;

/**
 * Build query string from a FilterState.
 * Only includes parameters that have values so the backend applies its own defaults for omitted ones.
 */
function buildQueryParams(filters: FilterState): string {
  const params = new URLSearchParams();

  if (filters.startDate) {
    params.set('start_date', filters.startDate);
  }
  if (filters.endDate) {
    params.set('end_date', filters.endDate);
  }
  if (filters.species.length > 0) {
    params.set('species', filters.species.join(','));
  }
  if (filters.statuses.length > 0) {
    params.set('conservation_status', filters.statuses.join(','));
  }

  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

/**
 * Generic fetch helper that calls an analytics endpoint with filters,
 * enforces a timeout, and unwraps the response envelope.
 */
async function fetchAnalytics<T>(
  path: string,
  filters: FilterState,
  accessToken: string | null,
): Promise<AnalyticsResponse<T>> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const url = `${API_ENDPOINT}${path}${buildQueryParams(filters)}`;
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

    return (await response.json()) as AnalyticsResponse<T>;
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('Request timed out. Please try again.');
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

/** Fetch sighting location aggregation data for the heatmap. */
export async function fetchLocationData(
  filters: FilterState,
  accessToken: string | null,
): Promise<AnalyticsResponse<LocationData>> {
  return fetchAnalytics<LocationData>('/analytics/locations', filters, accessToken);
}

/** Fetch species trend data for the line chart. */
export async function fetchTrendData(
  filters: FilterState,
  accessToken: string | null,
): Promise<AnalyticsResponse<TrendData>> {
  return fetchAnalytics<TrendData>('/analytics/trends', filters, accessToken);
}

/** Fetch conservation status breakdown data for the bar chart. */
export async function fetchStatusData(
  filters: FilterState,
  accessToken: string | null,
): Promise<AnalyticsResponse<StatusData>> {
  return fetchAnalytics<StatusData>('/analytics/status', filters, accessToken);
}
