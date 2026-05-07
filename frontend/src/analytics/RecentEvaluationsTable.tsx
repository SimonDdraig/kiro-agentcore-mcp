// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import React from 'react';
import Table from '@cloudscape-design/components/table';
import Box from '@cloudscape-design/components/box';
import type { EvaluationResult } from './evaluationTypes';
import { formatEvaluatorLabel, scoreColor } from './EvaluationScoreCards';

export interface RecentEvaluationsTableProps {
  evaluations: EvaluationResult[];
}

/** Format an ISO-8601 timestamp into a short human-readable string. */
function formatTimestamp(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

export function RecentEvaluationsTable({
  evaluations,
}: RecentEvaluationsTableProps): React.JSX.Element {
  return (
    <Table
      items={evaluations}
      columnDefinitions={[
        {
          id: 'prompt_summary',
          header: 'Prompt',
          cell: (item) => (
            <Box variant="p" fontSize="body-s">
              {item.prompt_summary}
            </Box>
          ),
          width: '40%',
        },
        {
          id: 'evaluator_name',
          header: 'Evaluator',
          cell: (item) => formatEvaluatorLabel(item.evaluator_name),
        },
        {
          id: 'score',
          header: 'Score',
          cell: (item) => (
            <Box color={scoreColor(item.score)} fontWeight="bold">
              {item.score.toFixed(2)}
            </Box>
          ),
        },
        {
          id: 'timestamp',
          header: 'Time',
          cell: (item) => formatTimestamp(item.timestamp),
        },
      ]}
      empty={
        <Box textAlign="center" padding="l" color="text-status-inactive">
          No recent evaluations yet.
        </Box>
      }
      variant="embedded"
      stripedRows
    />
  );
}
