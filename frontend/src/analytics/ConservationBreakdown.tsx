// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import React, { useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import Spinner from '@cloudscape-design/components/spinner';
import Alert from '@cloudscape-design/components/alert';
import Button from '@cloudscape-design/components/button';
import Box from '@cloudscape-design/components/box';
import type { FilterState, StatusData } from './analyticsTypes';
import { fetchStatusData } from './analyticsApi';
import { useAnalyticsData } from './SightingHeatmap';

/**
 * Color map for IUCN conservation statuses, ordered from most urgent (red)
 * to least urgent (green). Exported so property tests can validate ordering.
 */
export const STATUS_COLORS: Record<string, string> = {
  critically_endangered: '#d32f2f',
  endangered: '#f57c00',
  vulnerable: '#fbc02d',
  near_threatened: '#7cb342',
  least_concern: '#388e3c',
};

/** Canonical ordering of IUCN statuses from most to least threatened. */
const STATUS_ORDER: string[] = [
  'critically_endangered',
  'endangered',
  'vulnerable',
  'near_threatened',
  'least_concern',
];

/** Convert a snake_case status key to a human-readable label. */
export function formatStatusLabel(status: string): string {
  return status
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/** Row shape for the Recharts BarChart. */
export interface StatusChartRow {
  status: string;
  label: string;
  count: number;
  species: string[];
}

/**
 * Sort StatusData entries into canonical IUCN threat order and map to chart rows.
 * Statuses not in the canonical list are appended at the end.
 */
export function toChartRows(data: StatusData[]): StatusChartRow[] {
  const byStatus = new Map<string, StatusData>();
  for (const entry of data) {
    byStatus.set(entry.conservation_status, entry);
  }

  const rows: StatusChartRow[] = [];

  // Add known statuses in canonical order
  for (const status of STATUS_ORDER) {
    const entry = byStatus.get(status);
    if (entry) {
      rows.push({
        status: entry.conservation_status,
        label: formatStatusLabel(entry.conservation_status),
        count: entry.count,
        species: entry.species,
      });
      byStatus.delete(status);
    }
  }

  // Append any remaining statuses not in the canonical list
  for (const [, entry] of byStatus) {
    rows.push({
      status: entry.conservation_status,
      label: formatStatusLabel(entry.conservation_status),
      count: entry.count,
      species: entry.species,
    });
  }

  return rows;
}

export interface ConservationBreakdownProps {
  filters: FilterState;
  accessToken: string | null;
}

export function ConservationBreakdown({
  filters,
  accessToken,
}: ConservationBreakdownProps): React.JSX.Element {
  const { data, loading, error, retry } = useAnalyticsData(fetchStatusData, filters, accessToken);
  const rows = toChartRows(data);
  const [selectedStatus, setSelectedStatus] = useState<StatusChartRow | null>(null);

  const handleBarClick = (row: StatusChartRow): void => {
    setSelectedStatus((prev) => (prev?.status === row.status ? null : row));
  };

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
        header="Failed to load conservation status data"
        action={<Button onClick={retry}>Retry</Button>}
      >
        {error}
      </Alert>
    );
  }

  if (rows.length === 0) {
    return (
      <Box textAlign="center" padding="l" color="text-status-inactive">
        No conservation status data matches the current filters.
      </Box>
    );
  }

  return (
    <div>
      <ResponsiveContainer width="100%" height={350}>
        <BarChart data={rows} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="label" />
          <YAxis allowDecimals={false} />
          <Tooltip />
          <Bar
            dataKey="count"
            name="Sightings"
            onClick={(_data, index) => handleBarClick(rows[index])}
            style={{ cursor: 'pointer' }}
          >
            {rows.map((row) => (
              <Cell key={row.status} fill={STATUS_COLORS[row.status] ?? '#888888'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {selectedStatus && (
        <div
          style={{
            marginTop: 16,
            padding: 12,
            border: '1px solid #e0e0e0',
            borderRadius: 8,
          }}
        >
          <Box variant="h4">{formatStatusLabel(selectedStatus.status)} — Species</Box>
          {selectedStatus.species.length > 0 ? (
            <ul style={{ margin: '8px 0 0 0', paddingLeft: 20 }}>
              {selectedStatus.species.map((sp) => (
                <li key={sp}>{sp}</li>
              ))}
            </ul>
          ) : (
            <Box color="text-status-inactive" padding={{ top: 'xs' }}>
              No species recorded for this status.
            </Box>
          )}
        </div>
      )}
    </div>
  );
}
