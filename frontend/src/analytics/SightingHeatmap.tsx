// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import React, { useEffect, useRef, useCallback, useState } from 'react';
import { MapContainer, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet.heat';
import Spinner from '@cloudscape-design/components/spinner';
import Alert from '@cloudscape-design/components/alert';
import Button from '@cloudscape-design/components/button';
import Box from '@cloudscape-design/components/box';
import type { FilterState, LocationData, AnalyticsResponse } from './analyticsTypes';
import { fetchLocationData } from './analyticsApi';

/** Center of Australia for the default map view. */
const AUSTRALIA_CENTER: L.LatLngExpression = [-25.5, 134.5];
const DEFAULT_ZOOM = 4;
const MAP_HEIGHT = 400;

/**
 * Generic hook that manages loading / error / data state for an analytics fetch function.
 * Auto-fetches when filters or accessToken change.
 */
export function useAnalyticsData<T>(
  fetchFn: (filters: FilterState, accessToken: string | null) => Promise<AnalyticsResponse<T>>,
  filters: FilterState,
  accessToken: string | null,
): { data: T[]; loading: boolean; error: string | null; retry: () => void } {
  const [data, setData] = useState<T[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetchFn(filters, accessToken);
      setData(response.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred.');
      setData([]);
    } finally {
      setLoading(false);
    }
  }, [fetchFn, filters, accessToken]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  return { data, loading, error, retry: fetchData };
}

/**
 * Normalize LocationData entries to [lat, lng, intensity] triples.
 * Intensity is normalized so the maximum count maps to 1.0.
 */
export function toHeatPoints(locations: LocationData[]): L.HeatLatLngTuple[] {
  if (locations.length === 0) return [];
  const maxCount = Math.max(...locations.map((loc) => loc.count));
  if (maxCount === 0) return locations.map((loc) => [loc.latitude, loc.longitude, 0]);
  return locations.map((loc) => [loc.latitude, loc.longitude, loc.count / maxCount]);
}

/**
 * Custom react-leaflet wrapper that manages a leaflet.heat layer on the map.
 * Uses useMap() to access the Leaflet map instance and useEffect to
 * add / update / remove the heat layer when points change.
 */
function HeatLayer({ points }: { points: L.HeatLatLngTuple[] }): null {
  const map = useMap();
  const layerRef = useRef<L.HeatLayer | null>(null);

  useEffect(() => {
    const addOrUpdate = () => {
      // Guard: skip if the map container has zero size (canvas not ready)
      const size = map.getSize();
      if (size.x === 0 || size.y === 0) return;

      if (layerRef.current) {
        layerRef.current.setLatLngs(points);
      } else {
        layerRef.current = L.heatLayer(points, {
          radius: 25,
          blur: 15,
          maxZoom: 10,
        }).addTo(map);
      }
    };

    // If the map is already sized, add immediately; otherwise wait for first render
    const size = map.getSize();
    if (size.x > 0 && size.y > 0) {
      addOrUpdate();
    } else {
      map.once('moveend', addOrUpdate);
    }

    return () => {
      map.off('moveend', addOrUpdate);
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
        layerRef.current = null;
      }
    };
  }, [map, points]);

  return null;
}

/**
 * Calls map.invalidateSize() when the map container is resized from zero,
 * fixing the grey-tiles issue when the map initializes inside a hidden div.
 */
function InvalidateOnResize(): null {
  const map = useMap();

  useEffect(() => {
    const container = map.getContainer();
    const observer = new ResizeObserver(() => {
      map.invalidateSize();
    });
    observer.observe(container);
    // Also invalidate after a short delay to catch the initial display:none → block transition
    const timer = setTimeout(() => map.invalidateSize(), 100);
    return () => {
      observer.disconnect();
      clearTimeout(timer);
    };
  }, [map]);

  return null;
}

export interface SightingHeatmapProps {
  filters: FilterState;
  accessToken: string | null;
}

export function SightingHeatmap({ filters, accessToken }: SightingHeatmapProps): React.JSX.Element {
  const { data, loading, error, retry } = useAnalyticsData(fetchLocationData, filters, accessToken);
  const heatPoints = toHeatPoints(data);

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
        header="Failed to load heatmap data"
        action={<Button onClick={retry}>Retry</Button>}
      >
        {error}
      </Alert>
    );
  }

  if (data.length === 0) {
    return (
      <Box textAlign="center" padding="l" color="text-status-inactive">
        No sightings match the current filters.
      </Box>
    );
  }

  return (
    <div style={{ height: MAP_HEIGHT, width: '100%' }}>
      <MapContainer
        center={AUSTRALIA_CENTER}
        zoom={DEFAULT_ZOOM}
        style={{ height: '100%', width: '100%' }}
        scrollWheelZoom={true}
      >
        <InvalidateOnResize />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <HeatLayer points={heatPoints} />
      </MapContainer>
    </div>
  );
}
