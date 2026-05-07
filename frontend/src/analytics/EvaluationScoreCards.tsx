// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import React from 'react';
import Box from '@cloudscape-design/components/box';
import ColumnLayout from '@cloudscape-design/components/column-layout';
import type { EvaluationSummary } from './evaluationTypes';

/** Map evaluator names to user-friendly display labels. */
export function formatEvaluatorLabel(name: string): string {
  const labels: Record<string, string> = {
    'Builtin.Helpfulness': 'Helpfulness',
    'Builtin.ToolSelectionAccuracy': 'Tool Selection',
    BushRangerDomainRules: 'Custom',
  };
  return labels[name] ?? name;
}

/** Return a Cloudscape text color token based on score thresholds. */
export function scoreColor(
  score: number,
): 'text-status-success' | 'text-status-warning' | 'text-status-error' {
  if (score >= 0.7) return 'text-status-success';
  if (score >= 0.4) return 'text-status-warning';
  return 'text-status-error';
}

export interface EvaluationScoreCardsProps {
  summaries: EvaluationSummary[];
}

export function EvaluationScoreCards({ summaries }: EvaluationScoreCardsProps): React.JSX.Element {
  if (summaries.length === 0) {
    return (
      <Box textAlign="center" padding="l" color="text-status-inactive">
        No evaluation data available yet.
      </Box>
    );
  }

  return (
    <ColumnLayout columns={summaries.length} variant="text-grid">
      {summaries.map((s) => (
        <div key={s.evaluator_name}>
          <Box variant="awsui-key-label">{formatEvaluatorLabel(s.evaluator_name)}</Box>
          <Box variant="awsui-value-large" color={scoreColor(s.average_score)}>
            {s.average_score.toFixed(2)}
          </Box>
          <Box variant="small" color="text-body-secondary">
            {s.count} evaluation{s.count !== 1 ? 's' : ''}
          </Box>
        </div>
      ))}
    </ColumnLayout>
  );
}
