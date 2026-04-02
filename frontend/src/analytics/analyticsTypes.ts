// Copyright 2025 Bush Ranger AI Project. All rights reserved.

/** Filter state shared across all dashboard components. */
export interface FilterState {
  startDate: string; // ISO-8601 date, default: 12 months ago
  endDate: string; // ISO-8601 date, default: today
  species: string[]; // empty = all species
  statuses: string[]; // empty = all statuses
}

/** Response from GET /analytics/locations */
export interface LocationData {
  latitude: number;
  longitude: number;
  locationName: string;
  count: number;
}

/** Response from GET /analytics/trends */
export interface TrendData {
  month: string; // "YYYY-MM" format
  species: string;
  count: number;
}

/** Response from GET /analytics/status */
export interface StatusData {
  conservation_status: string;
  count: number;
  species: string[];
}

/** Consistent JSON envelope returned by all analytics endpoints. */
export interface AnalyticsResponse<T> {
  data: T[];
  count: number;
  filters_applied: {
    start_date: string;
    end_date: string;
    species: string[];
    conservation_status: string[];
  };
}
