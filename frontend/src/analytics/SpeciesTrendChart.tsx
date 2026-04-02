// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import Spinner from '@cloudscape-design/components/spinner';
import Alert from '@cloudscape-design/components/alert';
import Button from '@cloudscape-design/components/button';
import Box from '@cloudscape-design/components/box';
import type { FilterState, TrendData } from './analyticsTypes';
import { fetchTrendData } from './analyticsApi';
import { useAnalyticsData } from './SightingHeatmap';

/** Distinct colors assigned to species lines in the trend chart. */
const LINE_COLORS = [
  '#1f77b4',
  '#ff7f0e',
  '#2ca02c',
  '#d62728',
  '#9467bd',
  '#8c564b',
  '#e377c2',
  '#7f7f7f',
  '#bcbd22',
  '#17becf',
  '#aec7e8',
  '#ffbb78',
  '#98df8a',
  '#ff9896',
  '#c5b0d5',
];

/** Row shape after pivoting TrendData[] for Recharts. */
export interface TrendChartRow {
  month: string;
  [speciesKey: string]: string | number;
}

/**
 * Pivot flat TrendData[] into rows keyed by month, with one numeric field per species.
 * This is the format Recharts LineChart expects.
 */
export function pivotTrendData(data: TrendData[]): {
  rows: TrendChartRow[];
  speciesKeys: string[];
} {
  const monthMap = new Map<string, TrendChartRow>();
  const speciesSet = new Set<string>();

  for (const entry of data) {
    const key = entry.species === 'All' ? 'All Species' : entry.species;
    speciesSet.add(key);

    let row = monthMap.get(entry.month);
    if (!row) {
      row = { month: entry.month };
      monthMap.set(entry.month, row);
    }
    row[key] = entry.count;
  }

  // Sort rows chronologically by month
  const rows = Array.from(monthMap.values()).sort((a, b) => a.month.localeCompare(b.month));
  const speciesKeys = Array.from(speciesSet).sort();

  return { rows, speciesKeys };
}

export interface SpeciesTrendChartProps {
  filters: FilterState;
  accessToken: string | null;
}

export function SpeciesTrendChart({
  filters,
  accessToken,
}: SpeciesTrendChartProps): React.JSX.Element {
  const { data, loading, error, retry } = useAnalyticsData(fetchTrendData, filters, accessToken);
  const { rows, speciesKeys } = pivotTrendData(data);

  if (loading) {
    return (
      <Box textAlign="center" padding="l">
        <Spinner size="large" />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert
        type="error"
        header="Failed to load trend data"
        action={<Button onClick={retry}>Retry</Button>}
      >
        {error}
      </Alert>
    );
  }

  if (rows.length === 0) {
    return (
      <Box textAlign="center" padding="l" color="text-status-inactive">
        No trend data matches the current filters.
      </Box>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={350}>
      <LineChart data={rows} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="month" />
        <YAxis allowDecimals={false} />
        <Tooltip />
        <Legend />
        {speciesKeys.map((species, index) => (
          <Line
            key={species}
            type="monotone"
            dataKey={species}
            name={species}
            stroke={LINE_COLORS[index % LINE_COLORS.length]}
            activeDot={{ r: 6 }}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
