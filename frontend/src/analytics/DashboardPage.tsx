// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import React, { useState, useEffect, useCallback } from 'react';
import Button from '@cloudscape-design/components/button';
import Container from '@cloudscape-design/components/container';
import Header from '@cloudscape-design/components/header';
import Grid from '@cloudscape-design/components/grid';
import SpaceBetween from '@cloudscape-design/components/space-between';
import type { FilterState } from './analyticsTypes';
import type { EvaluationSummary, EvaluationResult, EvaluationTrendPoint } from './evaluationTypes';
import { FilterPanel, getDefaultFilters } from './FilterPanel';
import { SightingHeatmap } from './SightingHeatmap';
import { SpeciesTrendChart } from './SpeciesTrendChart';
import { ConservationBreakdown } from './ConservationBreakdown';
import { EvaluationScoreCards } from './EvaluationScoreCards';
import { EvaluationTrendChart } from './EvaluationTrendChart';
import { RecentEvaluationsTable } from './RecentEvaluationsTable';
import { fetchEvaluationSummary, fetchRecentEvaluations } from './evaluationsApi';
import { useAuth } from '../auth/AuthProvider';

/** The 30 Australian species from the seed dataset. */
const SPECIES_LIST: string[] = [
  'Bilby',
  'Black-flanked Rock-wallaby',
  'Brush-tailed Rock-wallaby',
  'Cassowary',
  'Dugong',
  'Eastern Grey Kangaroo',
  'Echidna',
  'Emu',
  'Frilled-neck Lizard',
  'Green Sea Turtle',
  'Helmeted Honeyeater',
  'Koala',
  'Kookaburra',
  "Leadbeater's Possum",
  'Mountain Pygmy-possum',
  'Numbat',
  'Orange-bellied Parrot',
  'Platypus',
  'Quokka',
  'Red Kangaroo',
  'Regent Honeyeater',
  'Saltwater Crocodile',
  'Spotted-tail Quoll',
  'Sugar Glider',
  'Sulphur-crested Cockatoo',
  'Swift Parrot',
  'Tasmanian Devil',
  'Wedge-tailed Eagle',
  'Western Swamp Tortoise',
  'Wombat',
];

/**
 * Derive trend data from recent evaluations by grouping scores by date and
 * evaluator name, then computing the average score per group.
 */
export function deriveTrendData(evaluations: EvaluationResult[]): EvaluationTrendPoint[] {
  const groups = new Map<string, { total: number; count: number }>();

  for (const ev of evaluations) {
    const date = ev.timestamp.slice(0, 10); // YYYY-MM-DD
    const key = `${date}|${ev.evaluator_name}`;
    const entry = groups.get(key);
    if (entry) {
      entry.total += ev.score;
      entry.count += 1;
    } else {
      groups.set(key, { total: ev.score, count: 1 });
    }
  }

  const points: EvaluationTrendPoint[] = [];
  for (const [key, { total, count }] of groups) {
    const [date, evaluator_name] = key.split('|');
    points.push({ date, evaluator_name, average_score: total / count, count });
  }
  return points;
}

export function DashboardPage(): React.JSX.Element {
  const { accessToken } = useAuth();
  const [filters, setFilters] = useState<FilterState>(getDefaultFilters);

  const [summaries, setSummaries] = useState<EvaluationSummary[]>([]);
  const [recentEvaluations, setRecentEvaluations] = useState<EvaluationResult[]>([]);
  const [evalLoading, setEvalLoading] = useState(false);

  const fetchEvalData = useCallback(async () => {
    setEvalLoading(true);
    const today = new Date().toISOString().slice(0, 10);
    const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
    try {
      const [summaryRes, recentRes] = await Promise.all([
        fetchEvaluationSummary(weekAgo, today, accessToken),
        fetchRecentEvaluations(20, accessToken),
      ]);
      setSummaries(summaryRes.data);
      setRecentEvaluations(recentRes.data);
    } catch {
      // Silent degradation — dashboard shows stale data on fetch failure
    } finally {
      setEvalLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    void fetchEvalData();
  }, [fetchEvalData]);

  const trendData = deriveTrendData(recentEvaluations);

  return (
    <SpaceBetween size="l">
      <Container header={<Header variant="h2">Sighting Analytics Dashboard</Header>}>
        <FilterPanel filters={filters} onFilterChange={setFilters} speciesList={SPECIES_LIST} />
      </Container>

      <Container header={<Header variant="h2">Sighting Heatmap</Header>}>
        <SightingHeatmap filters={filters} accessToken={accessToken} />
      </Container>

      <Grid
        gridDefinition={[{ colspan: { default: 12, m: 6 } }, { colspan: { default: 12, m: 6 } }]}
      >
        <Container header={<Header variant="h2">Species Trends</Header>}>
          <SpeciesTrendChart filters={filters} accessToken={accessToken} />
        </Container>
        <Container header={<Header variant="h2">Conservation Status Breakdown</Header>}>
          <ConservationBreakdown filters={filters} accessToken={accessToken} />
        </Container>
      </Grid>

      <Container
        header={
          <Header
            variant="h2"
            actions={
              <Button iconName="refresh" loading={evalLoading} onClick={() => void fetchEvalData()}>
                Refresh
              </Button>
            }
          >
            Agent Quality Metrics
          </Header>
        }
      >
        <SpaceBetween size="l">
          <EvaluationScoreCards summaries={summaries} />
          <EvaluationTrendChart trendData={trendData} />
          <RecentEvaluationsTable evaluations={recentEvaluations} />
        </SpaceBetween>
      </Container>
    </SpaceBetween>
  );
}
