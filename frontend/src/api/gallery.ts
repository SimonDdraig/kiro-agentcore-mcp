// Copyright 2025 Bush Ranger AI Project. All rights reserved.

const API_ENDPOINT = import.meta.env.VITE_API_ENDPOINT ?? '';

export interface GalleryImage {
  s3_key: string;
  prompt: string;
  timestamp: string;
  thumbnail_url: string;
  full_url: string;
}

export interface GalleryResponse {
  images: GalleryImage[];
  count: number;
}

/**
 * Fetch gallery images directly from the /gallery API endpoint.
 * Bypasses the agent for fast loading.
 */
export async function fetchGalleryImages(accessToken: string | null): Promise<GalleryResponse> {
  const response = await fetch(`${API_ENDPOINT}/gallery`, {
    method: 'GET',
    headers: {
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
  });

  if (!response.ok) {
    throw new Error(`Gallery API returned ${response.status}`);
  }

  return response.json() as Promise<GalleryResponse>;
}
