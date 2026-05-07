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
import Box from '@cloudscape-design/components/box';
import type { EvaluationTrendPoint } from './evaluationTypes';
import { formatEvaluatorLabel } from './EvaluationScoreCards';

/** Distinct colors assigned to evaluator lines in the trend chart. */
const LINE_COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd'];

/** Row shape after pivoting EvaluationTrendPoint[] for Recharts. */
export interface TrendRow {
  date: string;
  [evaluatorKey: string]: string | number;
}

/**
 * Pivot flat EvaluationTrendPoint[] into rows keyed by date, with one
 * numeric field per evaluator. This is the format Recharts LineChart expects.
 */
export function pivotTrendData(data: EvaluationTrendPoint[]): {
  rows: TrendRow[];
  evaluatorKeys: string[];
} {
  const dateMap = new Map<string, TrendRow>();
  const evaluatorSet = new Set<string>();

  for (const point of data) {
    const label = formatEvaluatorLabel(point.evaluator_name);
    evaluatorSet.add(label);

    let row = dateMap.get(point.date);
    if (!row) {
      row = { date: point.date };
      dateMap.set(point.date, row);
    }
    row[label] = point.average_score;
  }

  const rows = Array.from(dateMap.values()).sort((a, b) =>
    (a.date as string).localeCompare(b.date as string),
  );
  const evaluatorKeys = Array.from(evaluatorSet).sort();

  return { rows, evaluatorKeys };
}

export interface EvaluationTrendChartProps {
  trendData: EvaluationTrendPoint[];
}

export function EvaluationTrendChart({ trendData }: EvaluationTrendChartProps): React.JSX.Element {
  const { rows, evaluatorKeys } = pivotTrendData(trendData);

  if (rows.length === 0) {
    return (
      <Box textAlign="center" padding="l" color="text-status-inactive">
        No trend data available yet.
      </Box>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={350}>
      <LineChart data={rows} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" />
        <YAxis domain={[0, 1]} tickFormatter={(v: number) => v.toFixed(1)} />
        <Tooltip
          formatter={(value) =>
            typeof value === 'number' ? value.toFixed(2) : String(value ?? '')
          }
        />
        <Legend />
        {evaluatorKeys.map((evaluator, index) => (
          <Line
            key={evaluator}
            type="monotone"
            dataKey={evaluator}
            name={evaluator}
            stroke={LINE_COLORS[index % LINE_COLORS.length]}
            activeDot={{ r: 6 }}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
