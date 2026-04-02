# Implementation Plan: Sighting Analytics Dashboard

## Overview

Implement a read-only analytics dashboard for the Bush Ranger AI app. The work is split into backend (Python Lambda for aggregation endpoints), frontend (React/TypeScript with Cloudscape, Leaflet, and Recharts), CDK infrastructure, and navigation wiring. Each task builds incrementally so the feature is testable at every checkpoint.

## Tasks

- [x] 1. Define frontend types and API client
  - [x] 1.1 Create analytics type definitions and API client
    - Create `frontend/src/analytics/analyticsTypes.ts` with `FilterState`, `LocationData`, `TrendData`, `StatusData` interfaces
    - Create `frontend/src/analytics/analyticsApi.ts` with typed fetch functions `fetchLocationData`, `fetchTrendData`, `fetchStatusData` that accept `FilterState` and call the three GET endpoints with query parameters
    - Include the response envelope type (`{ data, count, filters_applied }`)
    - _Requirements: 6.4, 6.5_

- [x] 2. Implement the analytics Lambda backend
  - [x] 2.1 Create the analytics Lambda handler
    - Create `services/api/analytics_handler.py` with a single `handler` function that routes on `GET /analytics/locations`, `GET /analytics/trends`, `GET /analytics/status`
    - Parse optional query parameters: `start_date`, `end_date`, `species` (comma-separated), `conservation_status` (comma-separated)
    - Validate date formats (ISO-8601) and reject unknown parameters with 400
    - Return consistent JSON envelope `{ data, count, filters_applied }` with CORS headers
    - _Requirements: 6.4, 6.5, 6.6, 6.7_

  - [x] 2.2 Implement location aggregation endpoint
    - In `analytics_handler.py`, implement the `/analytics/locations` route
    - Scan `BushRangerSightings` table with optional date/species/status filters
    - Group results by latitude/longitude, count sightings per location, derive `locationName`
    - Return `LocationData[]` in the response envelope
    - _Requirements: 6.1_

  - [x] 2.3 Implement trends aggregation endpoint
    - In `analytics_handler.py`, implement the `/analytics/trends` route
    - Query by species partition key when species filter is provided; otherwise scan
    - Group results by species and month (`YYYY-MM`), return `TrendData[]`
    - When no species filter is applied, return aggregated totals across all species
    - _Requirements: 6.2, 3.5_

  - [x] 2.4 Implement status aggregation endpoint
    - In `analytics_handler.py`, implement the `/analytics/status` route
    - Query the `conservation_status-date-index` GSI by status with optional date range
    - Group by `conservation_status`, count sightings, collect contributing species list
    - Return `StatusData[]` in the response envelope
    - _Requirements: 6.3_

  - [x] 2.5 Write property tests for analytics backend
    - **Property 7: Aggregation count conservation** — sum of all `count` values equals total matching records
    - **Property 8: Filter application correctness** — every returned record satisfies all filter criteria, no valid record excluded
    - **Property 9: Response envelope consistency** — response contains `data` (array), `count` (== len(data)), `filters_applied`
    - **Property 10: Invalid parameters return 400** — malformed dates or unknown params yield HTTP 400 with `error` key
    - **Property 11: Read-only operations** — table contents unchanged after any request
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7**
    - Create tests in `tests/test_properties_analytics.py` using `hypothesis`

  - [x] 2.6 Write unit tests for analytics backend
    - Test location aggregation with a known dataset (Req 6.1)
    - Test trend aggregation with a known dataset (Req 6.2)
    - Test status aggregation with a known dataset (Req 6.3)
    - Test aggregated trend with no species filter returns totals (Req 3.5)
    - Test 400 response for invalid date format
    - Create tests in `tests/test_analytics.py` using `pytest`
    - _Requirements: 6.1, 6.2, 6.3, 6.6, 3.5_

- [x] 3. Checkpoint — Backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Add CDK infrastructure for analytics Lambda and API routes
  - [x] 4.1 Add analytics Lambda and API Gateway routes to CDK stack
    - In `infra/stacks/bush_ranger_stack.py`, create a new Lambda function `AnalyticsFunction` using `services/api/analytics_handler.py`
    - Grant read-only DynamoDB permissions (`dynamodb:Query`, `dynamodb:Scan`) on the sightings table and its GSI
    - Add three new API Gateway routes: `GET /analytics/locations`, `GET /analytics/trends`, `GET /analytics/status` with the existing JWT authorizer
    - Update CORS `allow_methods` to include `GET` alongside existing `POST`
    - Pass `TABLE_NAME`, `GSI_NAME`, `CORS_ORIGIN` as environment variables to the Lambda
    - _Requirements: 6.1, 6.2, 6.3, 6.7_

- [ ] 5. Install frontend dependencies and build the FilterPanel
  - [x] 5.1 Install new npm dependencies
    - Add `leaflet`, `react-leaflet`, `leaflet.heat`, `recharts` as dependencies
    - Add `@types/leaflet` as a devDependency
    - Add a type declaration file for `leaflet.heat` (no `@types` package exists)
    - _Requirements: 2.1, 3.1, 4.1_

  - [x] 5.2 Implement the FilterPanel component
    - Create `frontend/src/analytics/FilterPanel.tsx`
    - Use Cloudscape `DateRangePicker` for start/end date selection
    - Use Cloudscape `Multiselect` for species (populated from data) and IUCN status (5 fixed categories)
    - Add a reset button that restores defaults: all species, all statuses, last 12 months
    - Call `onFilterChange(filters: FilterState)` callback on any change
    - Validate start date ≤ end date
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 5.3 Write property test for filter reset
    - **Property 6: Filter reset restores defaults** — for any arbitrary FilterState, reset produces the default state
    - **Validates: Requirements 5.6**
    - Add to `tests/frontend/dashboard-properties.test.tsx` using `fast-check`

- [ ] 6. Implement the SightingHeatmap visualization
  - [x] 6.1 Implement the SightingHeatmap component
    - Create `frontend/src/analytics/SightingHeatmap.tsx`
    - Use `react-leaflet` `MapContainer` centered on Australia (lat -25.5, lng 134.5, zoom 4) with OpenStreetMap tiles
    - Create a custom `HeatLayer` wrapper component that integrates `leaflet.heat` with react-leaflet's layer lifecycle
    - Map `LocationData` entries to `[lat, lng, count]` triples for the heat layer
    - Import Leaflet CSS for proper map rendering
    - Show empty state message when no data matches filters
    - Manage loading/error/success state via a `useAnalyticsData` custom hook
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 7.1, 7.2, 7.3, 7.4_

  - [x] 6.2 Write property tests for heatmap
    - **Property 1: Heat layer intensity monotonicity** — higher count produces higher intensity value
    - **Property 2: Heat layer points contain valid coordinates** — lat in [-44, -10], lng in [112, 154]
    - **Validates: Requirements 2.2, 2.4**
    - Add to `tests/frontend/dashboard-properties.test.tsx` using `fast-check`

- [ ] 7. Implement the SpeciesTrendChart visualization
  - [x] 7.1 Implement the SpeciesTrendChart component
    - Create `frontend/src/analytics/SpeciesTrendChart.tsx`
    - Use Recharts `LineChart` with one `Line` per selected species, x-axis = months, y-axis = counts
    - Add `Tooltip` showing species name, month, and count on hover
    - When no species selected, show a single aggregated total line
    - Manage loading/error/success state independently
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 7.1, 7.2, 7.3, 7.4_

  - [x] 7.2 Write property test for trend lines
    - **Property 3: Trend lines match selected species** — exactly one line per selected species, none for unselected
    - **Validates: Requirements 3.3**
    - Add to `tests/frontend/dashboard-properties.test.tsx` using `fast-check`

- [ ] 8. Implement the ConservationBreakdown visualization
  - [x] 8.1 Implement the ConservationBreakdown component
    - Create `frontend/src/analytics/ConservationBreakdown.tsx`
    - Use Recharts `BarChart` with consistent color scheme (critically_endangered = red → least_concern = green)
    - On segment click, display a detail panel listing species in that IUCN category
    - Manage loading/error/success state independently
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 7.1, 7.2, 7.3, 7.4_

  - [x] 8.2 Write property tests for conservation breakdown
    - **Property 4: Conservation status color urgency ordering** — more threatened status gets more urgent color
    - **Property 5: Status detail species list accuracy** — species array matches exactly the species with that status in filtered data
    - **Validates: Requirements 4.3, 4.5**
    - Add to `tests/frontend/dashboard-properties.test.tsx` using `fast-check`

- [x] 9. Checkpoint — Frontend components compile and render
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Build the DashboardPage and wire navigation
  - [x] 10.1 Implement the DashboardPage component
    - Create `frontend/src/analytics/DashboardPage.tsx`
    - Manage shared `FilterState` and pass it to `FilterPanel`, `SightingHeatmap`, `SpeciesTrendChart`, `ConservationBreakdown`
    - Use Cloudscape `Grid` layout to arrange the visualizations
    - Create a `useAnalyticsData` custom hook encapsulating fetch, retry, and error state for each visualization
    - _Requirements: 2.3, 3.3, 4.4, 5.4, 7.1, 7.2, 7.3, 7.4_

  - [x] 10.2 Add SideNavigation and page routing in App.tsx
    - Update `frontend/src/App.tsx` to add Cloudscape `SideNavigation` with "Chat" and "Dashboard" items
    - Add `currentPage` state to control which page renders
    - Preserve dashboard state in memory when switching to Chat and back (keep DashboardPage mounted or cache state)
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 10.3 Write property test for independent visualization rendering
    - **Property 12: Independent visualization rendering** — visualizations backed by non-failing endpoints render correctly regardless of other endpoint failures
    - **Validates: Requirements 7.4**
    - Add to `tests/frontend/dashboard-properties.test.tsx` using `fast-check`

  - [x] 10.4 Write unit tests for dashboard navigation and error states
    - Test dashboard navigation renders correct page (Req 1.1)
    - Test dashboard not accessible when unauthenticated (Req 1.2)
    - Test dashboard state preserved on nav switch (Req 1.3)
    - Test loading indicators during fetch (Req 7.1)
    - Test error message and retry button on API failure (Req 7.2, 7.3)
    - Test heatmap empty state message (Req 2.5)
    - Test default filter values on load (Req 5.5)
    - Create tests in `tests/frontend/dashboard.test.tsx` using Vitest + Testing Library
    - _Requirements: 1.1, 1.2, 1.3, 2.5, 5.5, 7.1, 7.2, 7.3_

- [x] 11. Final checkpoint — All tests pass and feature is integrated
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Frontend uses TypeScript with React, Cloudscape, Leaflet, and Recharts
- Backend uses Python with boto3 for DynamoDB access
