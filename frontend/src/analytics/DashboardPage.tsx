// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import React, { useState } from 'react';
import Container from '@cloudscape-design/components/container';
import Header from '@cloudscape-design/components/header';
import Grid from '@cloudscape-design/components/grid';
import SpaceBetween from '@cloudscape-design/components/space-between';
import type { FilterState } from './analyticsTypes';
import { FilterPanel, getDefaultFilters } from './FilterPanel';
import { SightingHeatmap } from './SightingHeatmap';
import { SpeciesTrendChart } from './SpeciesTrendChart';
import { ConservationBreakdown } from './ConservationBreakdown';
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

export function DashboardPage(): React.JSX.Element {
  const { accessToken } = useAuth();
  const [filters, setFilters] = useState<FilterState>(getDefaultFilters);

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
    </SpaceBetween>
  );
}
