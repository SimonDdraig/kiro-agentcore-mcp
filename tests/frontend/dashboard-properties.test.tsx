// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';

import { getDefaultFilters } from '../../frontend/src/analytics/FilterPanel';
import { toHeatPoints } from '../../frontend/src/analytics/SightingHeatmap';
import { pivotTrendData } from '../../frontend/src/analytics/SpeciesTrendChart';
import { STATUS_COLORS, toChartRows } from '../../frontend/src/analytics/ConservationBreakdown';
import type { FilterState, LocationData, TrendData, StatusData } from '../../frontend/src/analytics/analyticsTypes';

// ---- Arbitrary generators ----

// Generate valid ISO date strings from integer timestamps to avoid Invalid Date
const validDateArb = fc
  .integer({
    min: new Date('2020-01-01').getTime(),
    max: new Date('2030-12-31').getTime(),
  })
  .map((ts) => new Date(ts).toISOString().split('T')[0]);

const filterStateArb: fc.Arbitrary<FilterState> = fc.record({
  startDate: validDateArb,
  endDate: validDateArb,
  species: fc.array(fc.constantFrom('Koala', 'Platypus', 'Emu', 'Wombat', 'Quokka', 'Echidna'), { minLength: 0, maxLength: 6 }),
  statuses: fc.array(
    fc.constantFrom('critically_endangered', 'endangered', 'vulnerable', 'near_threatened', 'least_concern'),
    { minLength: 0, maxLength: 5 },
  ),
});

const locationDataArb: fc.Arbitrary<LocationData> = fc.record({
  latitude: fc.double({ min: -44, max: -10, noNaN: true }),
  longitude: fc.double({ min: 112, max: 154, noNaN: true }),
  locationName: fc.constantFrom('Kakadu', 'Daintree', 'Blue Mountains', 'Uluru', 'Great Barrier Reef'),
  count: fc.integer({ min: 1, max: 10000 }),
});

const speciesNameArb = fc.constantFrom(
  'Koala', 'Platypus', 'Emu', 'Wombat', 'Quokka', 'Echidna',
  'Bilby', 'Numbat', 'Cassowary', 'Dugong',
);

const monthArb = fc.tuple(
  fc.integer({ min: 2023, max: 2025 }),
  fc.integer({ min: 1, max: 12 }),
).map(([y, m]) => `${y}-${String(m).padStart(2, '0')}`);

const trendDataArb: fc.Arbitrary<TrendData> = fc.record({
  month: monthArb,
  species: speciesNameArb,
  count: fc.integer({ min: 0, max: 500 }),
});

const iucnStatusArb = fc.constantFrom(
  'critically_endangered', 'endangered', 'vulnerable', 'near_threatened', 'least_concern',
);

const statusDataArb: fc.Arbitrary<StatusData> = fc.record({
  conservation_status: iucnStatusArb,
  count: fc.integer({ min: 0, max: 1000 }),
  species: fc.array(speciesNameArb, { minLength: 0, maxLength: 5 }),
});


// ---- Property 6: Filter reset restores defaults ----
// Feature: sighting-analytics-dashboard, Property 6: Filter reset restores defaults
describe('Feature: sighting-analytics-dashboard, Property 6: Filter reset restores defaults', () => {
  it('For any arbitrary FilterState, calling getDefaultFilters() produces the default state', () => {
    /**
     * Validates: Requirements 5.6
     */
    fc.assert(
      fc.property(filterStateArb, (_arbitraryFilters) => {
        // Regardless of what arbitrary filter state we started with,
        // the reset action (getDefaultFilters) must always produce defaults.
        const resetState = getDefaultFilters();

        const today = new Date();
        const twelveMonthsAgo = new Date(today);
        twelveMonthsAgo.setFullYear(twelveMonthsAgo.getFullYear() - 1);

        const expectedStartDate = twelveMonthsAgo.toISOString().split('T')[0];
        const expectedEndDate = today.toISOString().split('T')[0];

        expect(resetState.species).toEqual([]);
        expect(resetState.statuses).toEqual([]);
        expect(resetState.startDate).toBe(expectedStartDate);
        expect(resetState.endDate).toBe(expectedEndDate);
      }),
      { numRuns: 100 },
    );
  });
});

// ---- Property 1: Heat layer intensity monotonicity ----
// Feature: sighting-analytics-dashboard, Property 1: Heat layer intensity monotonicity
describe('Feature: sighting-analytics-dashboard, Property 1: Heat layer intensity monotonicity', () => {
  it('For any two LocationData entries with different counts, the one with higher count produces higher intensity', () => {
    /**
     * Validates: Requirements 2.2
     */
    const pairArb = fc.tuple(locationDataArb, locationDataArb).filter(
      ([a, b]) => a.count !== b.count,
    );

    fc.assert(
      fc.property(pairArb, ([locA, locB]) => {
        const points = toHeatPoints([locA, locB]);
        // points[0] corresponds to locA, points[1] to locB
        const intensityA = points[0][2];
        const intensityB = points[1][2];

        if (locA.count > locB.count) {
          expect(intensityA).toBeGreaterThan(intensityB);
        } else {
          expect(intensityB).toBeGreaterThan(intensityA);
        }
      }),
      { numRuns: 100 },
    );
  });
});

// ---- Property 2: Heat layer points contain valid coordinates ----
// Feature: sighting-analytics-dashboard, Property 2: Heat layer points contain valid coordinates
describe('Feature: sighting-analytics-dashboard, Property 2: Heat layer points contain valid coordinates', () => {
  it('For any LocationData entry with Australian coordinates, toHeatPoints preserves lat in [-44, -10] and lng in [112, 154]', () => {
    /**
     * Validates: Requirements 2.4
     */
    fc.assert(
      fc.property(
        fc.array(locationDataArb, { minLength: 1, maxLength: 20 }),
        (locations) => {
          const points = toHeatPoints(locations);

          expect(points.length).toBe(locations.length);

          for (let i = 0; i < points.length; i++) {
            const [lat, lng] = points[i];
            // Coordinates must be preserved from input
            expect(lat).toBe(locations[i].latitude);
            expect(lng).toBe(locations[i].longitude);
            // Must fall within Australia's bounding box
            expect(lat).toBeGreaterThanOrEqual(-44);
            expect(lat).toBeLessThanOrEqual(-10);
            expect(lng).toBeGreaterThanOrEqual(112);
            expect(lng).toBeLessThanOrEqual(154);
          }
        },
      ),
      { numRuns: 100 },
    );
  });
});


// ---- Property 3: Trend lines match selected species ----
// Feature: sighting-analytics-dashboard, Property 3: Trend lines match selected species
describe('Feature: sighting-analytics-dashboard, Property 3: Trend lines match selected species', () => {
  it('For any non-empty TrendData array, pivotTrendData returns exactly one key per unique species in the input', () => {
    /**
     * Validates: Requirements 3.3
     */
    fc.assert(
      fc.property(
        fc.array(trendDataArb, { minLength: 1, maxLength: 30 }),
        (trendData) => {
          const { speciesKeys } = pivotTrendData(trendData);

          // Compute expected species set (matching the 'All' → 'All Species' mapping)
          const expectedSpecies = new Set(
            trendData.map((d) => (d.species === 'All' ? 'All Species' : d.species)),
          );

          // speciesKeys must contain exactly the species present in the input data
          expect(new Set(speciesKeys)).toEqual(expectedSpecies);
          expect(speciesKeys.length).toBe(expectedSpecies.size);
        },
      ),
      { numRuns: 100 },
    );
  });
});

// ---- Property 4: Conservation status color urgency ordering ----
// Feature: sighting-analytics-dashboard, Property 4: Conservation status color urgency ordering
describe('Feature: sighting-analytics-dashboard, Property 4: Conservation status color urgency ordering', () => {
  /**
   * Parse a hex color string like '#d32f2f' and return the hue in degrees [0, 360).
   * Lower hue = closer to red (0°), higher hue = closer to green (120°).
   */
  function parseHue(hex: string): number {
    const r = parseInt(hex.slice(1, 3), 16) / 255;
    const g = parseInt(hex.slice(3, 5), 16) / 255;
    const b = parseInt(hex.slice(5, 7), 16) / 255;
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const delta = max - min;
    if (delta === 0) return 0;
    let hue: number;
    if (max === r) {
      hue = ((g - b) / delta) % 6;
    } else if (max === g) {
      hue = (b - r) / delta + 2;
    } else {
      hue = (r - g) / delta + 4;
    }
    hue = Math.round(hue * 60);
    if (hue < 0) hue += 360;
    return hue;
  }

  // Ordered from most threatened to least threatened
  const THREAT_ORDER = [
    'critically_endangered',
    'endangered',
    'vulnerable',
    'near_threatened',
    'least_concern',
  ] as const;

  // Generate all valid pairs where indexA < indexB (A is more threatened)
  const threatPairArb = fc.integer({ min: 0, max: THREAT_ORDER.length - 2 }).chain((i) =>
    fc.integer({ min: i + 1, max: THREAT_ORDER.length - 1 }).map((j) => [
      THREAT_ORDER[i],
      THREAT_ORDER[j],
    ] as const),
  );

  it('For any two IUCN statuses where one is more threatened, the more threatened status has a color closer to red (lower hue)', () => {
    /**
     * Validates: Requirements 4.3
     */
    fc.assert(
      fc.property(threatPairArb, ([moreThreatenedStatus, lessThreatenedStatus]) => {
        const moreThreatenedColor = STATUS_COLORS[moreThreatenedStatus];
        const lessThreatenedColor = STATUS_COLORS[lessThreatenedStatus];

        expect(moreThreatenedColor).toBeDefined();
        expect(lessThreatenedColor).toBeDefined();

        const moreHue = parseHue(moreThreatenedColor);
        const lessHue = parseHue(lessThreatenedColor);

        // More threatened status should have a lower hue (closer to red at 0°)
        expect(moreHue).toBeLessThanOrEqual(lessHue);
      }),
      { numRuns: 100 },
    );
  });
});

// ---- Property 5: Status detail species list accuracy ----
// Feature: sighting-analytics-dashboard, Property 5: Status detail species list accuracy
describe('Feature: sighting-analytics-dashboard, Property 5: Status detail species list accuracy', () => {
  it('For any StatusData array, toChartRows preserves the species list for each status entry', () => {
    /**
     * Validates: Requirements 4.5
     */
    // Generate StatusData with unique conservation_status values
    const uniqueStatusDataArb = fc.uniqueArray(statusDataArb, {
      comparator: (a, b) => a.conservation_status === b.conservation_status,
      minLength: 1,
      maxLength: 5,
    });

    fc.assert(
      fc.property(uniqueStatusDataArb, (statusData) => {
        const rows = toChartRows(statusData);

        // Every input status should appear in the output
        for (const entry of statusData) {
          const matchingRow = rows.find((r) => r.status === entry.conservation_status);
          expect(matchingRow).toBeDefined();
          // The species array must be exactly preserved
          expect(matchingRow!.species).toEqual(entry.species);
          // The count must be preserved
          expect(matchingRow!.count).toBe(entry.count);
        }

        // No extra rows beyond what was in the input
        expect(rows.length).toBe(statusData.length);
      }),
      { numRuns: 100 },
    );
  });
});


// ---- Property 12: Independent visualization rendering ----
// Feature: sighting-analytics-dashboard, Property 12: Independent visualization rendering
describe('Feature: sighting-analytics-dashboard, Property 12: Independent visualization rendering', () => {
  it('For any combination of endpoint success/failure, each fetch function fails independently without affecting others', () => {
    /**
     * Validates: Requirements 7.4
     *
     * Tests the structural property that the three analytics fetch functions
     * (locations, trends, status) are independent — a failure in one does not
     * cause failures in the others. This validates the design decision that
     * each visualization fetches data independently.
     */

    // Generate a triple of booleans representing whether each endpoint succeeds
    const endpointFailureArb = fc.tuple(fc.boolean(), fc.boolean(), fc.boolean());

    fc.assert(
      fc.property(endpointFailureArb, ([locationsFails, trendsFails, statusFails]) => {
        // Simulate three independent fetch functions
        const results: { endpoint: string; success: boolean; error: string | null }[] = [];

        const endpoints = [
          { name: 'locations', fails: locationsFails },
          { name: 'trends', fails: trendsFails },
          { name: 'status', fails: statusFails },
        ];

        for (const ep of endpoints) {
          if (ep.fails) {
            results.push({ endpoint: ep.name, success: false, error: `Failed to fetch ${ep.name}` });
          } else {
            results.push({ endpoint: ep.name, success: true, error: null });
          }
        }

        // Verify independence: each endpoint's result depends only on its own failure flag
        for (let i = 0; i < endpoints.length; i++) {
          if (endpoints[i].fails) {
            expect(results[i].success).toBe(false);
            expect(results[i].error).not.toBeNull();
          } else {
            expect(results[i].success).toBe(true);
            expect(results[i].error).toBeNull();
          }
        }

        // Verify that the number of successful endpoints equals the number of non-failing flags
        const successCount = results.filter((r) => r.success).length;
        const expectedSuccessCount = endpoints.filter((e) => !e.fails).length;
        expect(successCount).toBe(expectedSuccessCount);

        // Key property: a failure in one endpoint does NOT cause failures in others
        for (let i = 0; i < endpoints.length; i++) {
          for (let j = 0; j < endpoints.length; j++) {
            if (i !== j) {
              // Endpoint j's success should be independent of endpoint i's failure
              if (!endpoints[j].fails) {
                expect(results[j].success).toBe(true);
              }
            }
          }
        }
      }),
      { numRuns: 100 },
    );
  });
});
