// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import * as fc from 'fast-check';

import { formatDate } from '../../frontend/src/gallery/GalleryPage';
import type { GalleryImage } from '../../frontend/src/gallery/GalleryPage';

// ---- Mocks ----

const mockUseAuth = vi.fn();
vi.mock('../../frontend/src/auth/AuthProvider', () => ({
  useAuth: () => mockUseAuth(),
}));

const mockFetchGalleryImages = vi.fn();
vi.mock('../../frontend/src/api/gallery', () => ({
  fetchGalleryImages: (...args: unknown[]) => mockFetchGalleryImages(...args),
}));

// Import after mocks
const { GalleryPage } = await import('../../frontend/src/gallery/GalleryPage');

// ---- Arbitrary generators ----

const isoTimestampArb = fc
  .integer({
    min: new Date('2020-01-01T00:00:00Z').getTime(),
    max: new Date('2030-12-31T23:59:59Z').getTime(),
  })
  .map((ts) => new Date(ts).toISOString());

const promptArb = fc
  .array(
    fc.constantFrom(
      ...'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 '.split(''),
    ),
    { minLength: 3, maxLength: 80 },
  )
  .map((chars) => chars.join(''))
  .filter((s) => s.trim().length > 0);

const jobIdArb = fc.uuid();

const galleryImageArb: fc.Arbitrary<GalleryImage> = fc
  .record({
    jobId: jobIdArb,
    prompt: promptArb,
    timestamp: isoTimestampArb,
  })
  .map(({ jobId, prompt, timestamp }) => ({
    s3_key: `ArtGallery/${jobId}.png`,
    prompt,
    timestamp,
    thumbnail_url: `https://example.cloudfront.net/ArtGallery/${jobId}_thumb.png`,
    full_url: `https://example.cloudfront.net/ArtGallery/${jobId}.png`,
  }));

// ---- Property 9: Gallery card renders prompt and date ----
describe('Feature: art-gallery, Property 9: Gallery card renders prompt and date', () => {
  it('For any gallery entry with a non-empty prompt and valid timestamp, the rendered card displays the prompt text and formatted date', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(galleryImageArb, { minLength: 1, maxLength: 3 }),
        async (images) => {
          mockUseAuth.mockReturnValue({
            isAuthenticated: true,
            isLoading: false,
            accessToken: 'mock-token',
            signIn: vi.fn(),
            signOut: vi.fn(),
            refreshSession: vi.fn(),
          });

          mockFetchGalleryImages.mockResolvedValue({
            images,
            count: images.length,
          });

          const { container, unmount } = render(<GalleryPage />);

          await waitFor(() => {
            expect(container.textContent).toContain(images[0].prompt);
          });

          for (const image of images) {
            expect(container.textContent).toContain(image.prompt);
            const expectedDate = formatDate(image.timestamp);
            expect(container.textContent).toContain(expectedDate);
          }

          unmount();
          mockFetchGalleryImages.mockReset();
        },
      ),
      { numRuns: 100 },
    );
  });
});
