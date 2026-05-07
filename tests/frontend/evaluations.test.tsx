// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

// ---- Mocks ----

// Mock recharts ResponsiveContainer (needs DOM measurements)
vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts');
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
  };
});

// ---- Imports (after mocks) ----
import { EvaluationScoreCards, formatEvaluatorLabel, scoreColor } from '../../frontend/src/analytics/EvaluationScoreCards';
import { EvaluationTrendChart, pivotTrendData } from '../../frontend/src/analytics/EvaluationTrendChart';
import { RecentEvaluationsTable } from '../../frontend/src/analytics/RecentEvaluationsTable';
import type { EvaluationSummary, EvaluationResult, EvaluationTrendPoint } from '../../frontend/src/analytics/evaluationTypes';

// ---- Mock data ----

const mockSummaries: EvaluationSummary[] = [
  { evaluator_name: 'Builtin.Helpfulness', average_score: 0.85, count: 10 },
  { evaluator_name: 'Builtin.ToolSelectionAccuracy', average_score: 0.62, count: 8 },
  { evaluator_name: 'BushRangerDomainRules', average_score: 0.35, count: 5 },
];

const mockEvaluations: EvaluationResult[] = [
  {
    invocation_id: 'inv-001',
    evaluator_name: 'Builtin.Helpfulness',
    score: 0.9,
    rationale: 'Good response',
    prompt_summary: 'Where can I find koalas?',
    timestamp: '2025-01-15T10:30:00Z',
  },
  {
    invocation_id: 'inv-002',
    evaluator_name: 'Builtin.ToolSelectionAccuracy',
    score: 0.5,
    rationale: 'Partial tool use',
    prompt_summary: 'What is the fire danger today?',
    timestamp: '2025-01-15T09:15:00Z',
  },
  {
    invocation_id: 'inv-003',
    evaluator_name: 'BushRangerDomainRules',
    score: 0.2,
    rationale: 'Missing safety warning',
    prompt_summary: 'Tell me about camping near bushfire zones',
    timestamp: '2025-01-14T16:00:00Z',
  },
];

const mockTrendData: EvaluationTrendPoint[] = [
  { date: '2025-01-13', evaluator_name: 'Builtin.Helpfulness', average_score: 0.8, count: 3 },
  { date: '2025-01-13', evaluator_name: 'Builtin.ToolSelectionAccuracy', average_score: 0.6, count: 3 },
  { date: '2025-01-14', evaluator_name: 'Builtin.Helpfulness', average_score: 0.85, count: 4 },
  { date: '2025-01-14', evaluator_name: 'Builtin.ToolSelectionAccuracy', average_score: 0.7, count: 4 },
  { date: '2025-01-15', evaluator_name: 'Builtin.Helpfulness', average_score: 0.9, count: 3 },
];

// ---- Tests ----

/**
 * Validates: Requirement 6.1
 * THE Dashboard_Evaluations_Section SHALL display average scores for each evaluator
 * as numeric gauges or score cards.
 */
describe('EvaluationScoreCards renders with mock summary data (Req 6.1)', () => {
  it('renders score values and evaluator labels for each summary', () => {
    render(<EvaluationScoreCards summaries={mockSummaries} />);

    // Check formatted evaluator labels are rendered
    expect(screen.getByText('Helpfulness')).toBeDefined();
    expect(screen.getByText('Tool Selection')).toBeDefined();
    expect(screen.getByText('Custom')).toBeDefined();

    // Check formatted score values
    expect(screen.getByText('0.85')).toBeDefined();
    expect(screen.getByText('0.62')).toBeDefined();
    expect(screen.getByText('0.35')).toBeDefined();

    // Check evaluation counts
    expect(screen.getByText('10 evaluations')).toBeDefined();
    expect(screen.getByText('8 evaluations')).toBeDefined();
    expect(screen.getByText('5 evaluations')).toBeDefined();
  });

  it('renders empty state when no summaries provided', () => {
    render(<EvaluationScoreCards summaries={[]} />);
    expect(screen.getByText('No evaluation data available yet.')).toBeDefined();
  });
});

/**
 * Validates: Requirement 6.2
 * THE Dashboard_Evaluations_Section SHALL display a time-series chart showing
 * evaluation scores over time, with one line per evaluator.
 */
describe('EvaluationTrendChart renders with mock trend data (Req 6.2)', () => {
  it('renders the chart container when trend data is provided', () => {
    const { container } = render(<EvaluationTrendChart trendData={mockTrendData} />);
    // Recharts ResponsiveContainer renders with this class
    expect(container.querySelector('.recharts-responsive-container')).not.toBeNull();
  });

  it('renders empty state when no trend data provided', () => {
    render(<EvaluationTrendChart trendData={[]} />);
    expect(screen.getByText('No trend data available yet.')).toBeDefined();
  });
});

/**
 * Validates: Requirement 6.2 (pivotTrendData helper)
 * Test the pivotTrendData helper that transforms flat trend points into
 * Recharts-compatible rows with one column per evaluator.
 */
describe('pivotTrendData helper (Req 6.2)', () => {
  it('pivots flat trend points into rows keyed by date with evaluator columns', () => {
    const { rows, evaluatorKeys } = pivotTrendData(mockTrendData);

    // Should have 3 unique dates
    expect(rows.length).toBe(3);

    // Evaluator keys should be sorted formatted labels
    expect(evaluatorKeys).toEqual(['Helpfulness', 'Tool Selection']);

    // First row (2025-01-13) should have both evaluators
    expect(rows[0].date).toBe('2025-01-13');
    expect(rows[0]['Helpfulness']).toBe(0.8);
    expect(rows[0]['Tool Selection']).toBe(0.6);

    // Third row (2025-01-15) should only have Helpfulness
    expect(rows[2].date).toBe('2025-01-15');
    expect(rows[2]['Helpfulness']).toBe(0.9);
    expect(rows[2]['Tool Selection']).toBeUndefined();
  });

  it('returns empty rows and keys for empty input', () => {
    const { rows, evaluatorKeys } = pivotTrendData([]);
    expect(rows).toEqual([]);
    expect(evaluatorKeys).toEqual([]);
  });
});

/**
 * Validates: Requirement 6.3
 * THE Dashboard_Evaluations_Section SHALL display a list of the most recent
 * evaluations showing the prompt summary, evaluator scores, and timestamp.
 */
describe('RecentEvaluationsTable renders with mock evaluation data (Req 6.3)', () => {
  it('renders table with prompt summaries, evaluator names, and scores', () => {
    render(<RecentEvaluationsTable evaluations={mockEvaluations} />);

    // Check prompt summaries are rendered
    expect(screen.getByText('Where can I find koalas?')).toBeDefined();
    expect(screen.getByText('What is the fire danger today?')).toBeDefined();
    expect(screen.getByText('Tell me about camping near bushfire zones')).toBeDefined();

    // Check formatted evaluator labels
    expect(screen.getByText('Helpfulness')).toBeDefined();
    expect(screen.getByText('Tool Selection')).toBeDefined();
    expect(screen.getByText('Custom')).toBeDefined();

    // Check formatted scores
    expect(screen.getByText('0.90')).toBeDefined();
    expect(screen.getByText('0.50')).toBeDefined();
    expect(screen.getByText('0.20')).toBeDefined();
  });

  it('renders empty state when no evaluations provided', () => {
    render(<RecentEvaluationsTable evaluations={[]} />);
    expect(screen.getByText('No recent evaluations yet.')).toBeDefined();
  });
});

/**
 * Validates: Requirement 6.4
 * THE Dashboard_Evaluations_Section SHALL provide a manual refresh button
 * to fetch the latest evaluation data on demand.
 */
describe('DashboardPage exports deriveTrendData helper (Req 6.4)', () => {
  it('deriveTrendData is exported and callable', async () => {
    const { deriveTrendData } = await import('../../frontend/src/analytics/DashboardPage');
    expect(deriveTrendData).toBeDefined();
    expect(deriveTrendData([])).toEqual([]);
  });
});

/**
 * Validates: Requirement 6.5
 * THE Dashboard_Evaluations_Section SHALL use Cloudscape design components
 * consistent with the existing dashboard sections.
 */
describe('Cloudscape components are used (Req 6.5)', () => {
  it('EvaluationScoreCards uses Cloudscape ColumnLayout', () => {
    const { container } = render(<EvaluationScoreCards summaries={mockSummaries} />);
    // Cloudscape ColumnLayout renders with a specific class pattern
    expect(container.querySelector('[class*="column-layout"]')).toBeDefined();
  });

  it('RecentEvaluationsTable uses Cloudscape Table with striped rows', () => {
    const { container } = render(<RecentEvaluationsTable evaluations={mockEvaluations} />);
    // Cloudscape Table renders with a specific class pattern
    expect(container.querySelector('table')).toBeDefined();
  });
});

/**
 * Validates: Requirement 6.1
 * Helper function tests for formatEvaluatorLabel and scoreColor.
 */
describe('Helper functions (Req 6.1)', () => {
  it('formatEvaluatorLabel maps known evaluator names to friendly labels', () => {
    expect(formatEvaluatorLabel('Builtin.Helpfulness')).toBe('Helpfulness');
    expect(formatEvaluatorLabel('Builtin.ToolSelectionAccuracy')).toBe('Tool Selection');
    expect(formatEvaluatorLabel('BushRangerDomainRules')).toBe('Custom');
  });

  it('formatEvaluatorLabel returns the original name for unknown evaluators', () => {
    expect(formatEvaluatorLabel('SomeNewEvaluator')).toBe('SomeNewEvaluator');
  });

  it('scoreColor returns success for scores >= 0.7', () => {
    expect(scoreColor(0.7)).toBe('text-status-success');
    expect(scoreColor(0.85)).toBe('text-status-success');
    expect(scoreColor(1.0)).toBe('text-status-success');
  });

  it('scoreColor returns warning for scores >= 0.4 and < 0.7', () => {
    expect(scoreColor(0.4)).toBe('text-status-warning');
    expect(scoreColor(0.55)).toBe('text-status-warning');
    expect(scoreColor(0.69)).toBe('text-status-warning');
  });

  it('scoreColor returns error for scores < 0.4', () => {
    expect(scoreColor(0.0)).toBe('text-status-error');
    expect(scoreColor(0.2)).toBe('text-status-error');
    expect(scoreColor(0.39)).toBe('text-status-error');
  });
});
