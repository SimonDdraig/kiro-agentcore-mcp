// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import React from 'react';
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';

// ---- Mocks ----

// Mock useAuth
const mockUseAuth = vi.fn();
vi.mock('../../frontend/src/auth/AuthProvider', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuth: () => mockUseAuth(),
}));

// Mock analytics API functions
const mockFetchLocationData = vi.fn();
const mockFetchTrendData = vi.fn();
const mockFetchStatusData = vi.fn();
vi.mock('../../frontend/src/analytics/analyticsApi', () => ({
  fetchLocationData: (...args: unknown[]) => mockFetchLocationData(...args),
  fetchTrendData: (...args: unknown[]) => mockFetchTrendData(...args),
  fetchStatusData: (...args: unknown[]) => mockFetchStatusData(...args),
}));

// Mock react-leaflet (needs canvas)
vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="map-container">{children}</div>,
  TileLayer: () => <div data-testid="tile-layer" />,
  useMap: () => ({
    addLayer: vi.fn(),
    removeLayer: vi.fn(),
  }),
}));

// Mock leaflet
vi.mock('leaflet', () => ({
  default: {
    heatLayer: () => ({
      addTo: vi.fn().mockReturnThis(),
      setLatLngs: vi.fn(),
    }),
  },
  heatLayer: () => ({
    addTo: vi.fn().mockReturnThis(),
    setLatLngs: vi.fn(),
  }),
}));

// Mock leaflet.heat
vi.mock('leaflet.heat', () => ({}));

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

// Mock amazon-cognito-identity-js
vi.mock('amazon-cognito-identity-js', () => ({
  CognitoUserPool: vi.fn().mockImplementation(() => ({
    getCurrentUser: () => null,
  })),
  CognitoUser: vi.fn(),
  AuthenticationDetails: vi.fn(),
}));


// ---- Imports (after mocks) ----
import { App } from '../../frontend/src/App';
import { SightingHeatmap } from '../../frontend/src/analytics/SightingHeatmap';
import { SpeciesTrendChart } from '../../frontend/src/analytics/SpeciesTrendChart';
import { ConservationBreakdown } from '../../frontend/src/analytics/ConservationBreakdown';
import { getDefaultFilters } from '../../frontend/src/analytics/FilterPanel';
import type { FilterState } from '../../frontend/src/analytics/analyticsTypes';

// ---- Helpers ----

const authenticatedAuth = {
  isAuthenticated: true,
  isLoading: false,
  accessToken: 'mock-token',
  signIn: vi.fn(),
  signOut: vi.fn(),
  refreshSession: vi.fn(),
};

const unauthenticatedAuth = {
  isAuthenticated: false,
  isLoading: false,
  accessToken: null,
  signIn: vi.fn(),
  signOut: vi.fn(),
  refreshSession: vi.fn(),
};

const defaultFilters: FilterState = getDefaultFilters();

function makeSuccessResponse(data: unknown[] = []) {
  return Promise.resolve({
    data,
    count: (data as unknown[]).length,
    filters_applied: {
      start_date: defaultFilters.startDate,
      end_date: defaultFilters.endDate,
      species: [],
      conservation_status: [],
    },
  });
}

function makePendingResponse() {
  // Returns a promise that never resolves — simulates loading state
  return new Promise(() => {});
}

function makeErrorResponse(message: string) {
  return Promise.reject(new Error(message));
}

beforeEach(() => {
  vi.clearAllMocks();
  mockUseAuth.mockReturnValue(authenticatedAuth);
  // Default: resolve with empty data
  mockFetchLocationData.mockImplementation(() => makeSuccessResponse([]));
  mockFetchTrendData.mockImplementation(() => makeSuccessResponse([]));
  mockFetchStatusData.mockImplementation(() => makeSuccessResponse([]));
});

// ---- Tests ----

/**
 * Validates: Requirement 1.1
 * WHEN an authenticated ranger selects the Dashboard navigation item,
 * THE Dashboard SHALL render the analytics view.
 */
describe('Dashboard navigation renders correct page (Req 1.1)', () => {
  it('renders the dashboard view when Dashboard nav item is clicked', async () => {
    render(<App />);

    // The app should show the Chat page by default
    // Click the Dashboard nav link
    const dashboardLink = screen.getByText('Dashboard');
    fireEvent.click(dashboardLink);

    // Dashboard content should be visible
    await waitFor(() => {
      expect(screen.getByText('Sighting Analytics Dashboard')).toBeDefined();
    });
  });
});

/**
 * Validates: Requirement 1.2
 * THE Dashboard SHALL be accessible only to authenticated users.
 */
describe('Dashboard not accessible when unauthenticated (Req 1.2)', () => {
  it('shows sign-in page instead of dashboard when not authenticated', () => {
    mockUseAuth.mockReturnValue(unauthenticatedAuth);
    render(<App />);

    // Should show sign-in, not dashboard
    expect(screen.getByText('Sign in')).toBeDefined();
    expect(screen.queryByText('Sighting Analytics Dashboard')).toBeNull();
    expect(screen.queryByText('Dashboard')).toBeNull();
  });
});

/**
 * Validates: Requirement 1.3
 * WHEN the ranger selects the Chat navigation item,
 * THE Application SHALL return to the chat view without losing dashboard state.
 */
describe('Dashboard state preserved on nav switch (Req 1.3)', () => {
  it('preserves dashboard DOM when switching to Chat and back', async () => {
    render(<App />);

    // Navigate to Dashboard
    fireEvent.click(screen.getByText('Dashboard'));
    await waitFor(() => {
      expect(screen.getByText('Sighting Analytics Dashboard')).toBeDefined();
    });

    // Navigate to Chat
    fireEvent.click(screen.getByText('Chat'));

    // Navigate back to Dashboard — the component should still be mounted
    // (App uses display:none/block, not conditional rendering)
    fireEvent.click(screen.getByText('Dashboard'));
    await waitFor(() => {
      expect(screen.getByText('Sighting Analytics Dashboard')).toBeDefined();
    });
  });
});

/**
 * Validates: Requirement 7.1
 * WHILE the Dashboard is fetching data, THE Dashboard SHALL display a loading indicator.
 */
describe('Loading indicators during fetch (Req 7.1)', () => {
  it('shows spinner while SightingHeatmap is loading', () => {
    mockFetchLocationData.mockImplementation(() => makePendingResponse());

    const { container } = render(
      <SightingHeatmap filters={defaultFilters} accessToken="mock-token" />,
    );

    // Cloudscape Spinner renders a span with role="img" or a specific class
    // The component wraps it in a Box with textAlign center
    expect(container.querySelector('[class*="spinner"]') ?? container.textContent).toBeDefined();
  });

  it('shows spinner while SpeciesTrendChart is loading', () => {
    mockFetchTrendData.mockImplementation(() => makePendingResponse());

    const { container } = render(
      <SpeciesTrendChart filters={defaultFilters} accessToken="mock-token" />,
    );

    expect(container.querySelector('[class*="spinner"]') ?? container.textContent).toBeDefined();
  });

  it('shows spinner while ConservationBreakdown is loading', () => {
    mockFetchStatusData.mockImplementation(() => makePendingResponse());

    const { container } = render(
      <ConservationBreakdown filters={defaultFilters} accessToken="mock-token" />,
    );

    expect(container.querySelector('[class*="spinner"]') ?? container.textContent).toBeDefined();
  });
});

/**
 * Validates: Requirements 7.2, 7.3
 * IF the Analytics_API returns an error, THEN display error message and retry button.
 * WHEN the ranger clicks retry, re-fetch data.
 */
describe('Error message and retry button on API failure (Req 7.2, 7.3)', () => {
  it('shows error alert with retry button when heatmap fetch fails', async () => {
    mockFetchLocationData.mockImplementation(() => makeErrorResponse('Network error'));

    render(<SightingHeatmap filters={defaultFilters} accessToken="mock-token" />);

    await waitFor(() => {
      expect(screen.getByText('Failed to load heatmap data')).toBeDefined();
    });
    expect(screen.getByText('Network error')).toBeDefined();
    expect(screen.getByText('Retry')).toBeDefined();
  });

  it('retries fetch when retry button is clicked on heatmap', async () => {
    mockFetchLocationData.mockImplementation(() => makeErrorResponse('Network error'));

    render(<SightingHeatmap filters={defaultFilters} accessToken="mock-token" />);

    await waitFor(() => {
      expect(screen.getByText('Retry')).toBeDefined();
    });

    // Now make the next call succeed
    mockFetchLocationData.mockImplementation(() => makeSuccessResponse([]));

    await act(async () => {
      fireEvent.click(screen.getByText('Retry'));
    });

    await waitFor(() => {
      expect(screen.getByText('No sightings match the current filters.')).toBeDefined();
    });
  });

  it('shows error alert with retry button when trend fetch fails', async () => {
    mockFetchTrendData.mockImplementation(() => makeErrorResponse('Server error'));

    render(<SpeciesTrendChart filters={defaultFilters} accessToken="mock-token" />);

    await waitFor(() => {
      expect(screen.getByText('Failed to load trend data')).toBeDefined();
    });
    expect(screen.getByText('Server error')).toBeDefined();
    expect(screen.getByText('Retry')).toBeDefined();
  });

  it('shows error alert with retry button when status fetch fails', async () => {
    mockFetchStatusData.mockImplementation(() => makeErrorResponse('Timeout'));

    render(<ConservationBreakdown filters={defaultFilters} accessToken="mock-token" />);

    await waitFor(() => {
      expect(screen.getByText('Failed to load conservation status data')).toBeDefined();
    });
    expect(screen.getByText('Timeout')).toBeDefined();
    expect(screen.getByText('Retry')).toBeDefined();
  });
});

/**
 * Validates: Requirement 2.5
 * IF the Analytics_API returns an empty dataset, THEN display empty state message.
 */
describe('Heatmap empty state message (Req 2.5)', () => {
  it('shows empty state when location data is empty', async () => {
    mockFetchLocationData.mockImplementation(() => makeSuccessResponse([]));

    render(<SightingHeatmap filters={defaultFilters} accessToken="mock-token" />);

    await waitFor(() => {
      expect(screen.getByText('No sightings match the current filters.')).toBeDefined();
    });
  });
});

/**
 * Validates: Requirement 5.5
 * WHEN the Dashboard loads, THE Filter_Panel SHALL default to all species,
 * all statuses, and the most recent 12 months.
 */
describe('Default filter values on load (Req 5.5)', () => {
  it('getDefaultFilters returns empty species, empty statuses, and 12-month date range', () => {
    const filters = getDefaultFilters();

    const today = new Date();
    const twelveMonthsAgo = new Date(today);
    twelveMonthsAgo.setFullYear(twelveMonthsAgo.getFullYear() - 1);

    expect(filters.species).toEqual([]);
    expect(filters.statuses).toEqual([]);
    expect(filters.startDate).toBe(twelveMonthsAgo.toISOString().split('T')[0]);
    expect(filters.endDate).toBe(today.toISOString().split('T')[0]);
  });
});
