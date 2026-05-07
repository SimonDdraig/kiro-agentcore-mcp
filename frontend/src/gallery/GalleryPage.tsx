// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import React, { useState, useEffect, useCallback } from 'react';
import Box from '@cloudscape-design/components/box';
import Button from '@cloudscape-design/components/button';
import Cards from '@cloudscape-design/components/cards';
import Header from '@cloudscape-design/components/header';
import Modal from '@cloudscape-design/components/modal';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Spinner from '@cloudscape-design/components/spinner';
import Alert from '@cloudscape-design/components/alert';
import { fetchGalleryImages } from '../api/gallery';
import type { GalleryImage } from '../api/gallery';
import { useAuth } from '../auth/AuthProvider';

export type { GalleryImage };

/** Format an ISO 8601 timestamp into a human-readable date string. */
export function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return iso;
  }
}

export function GalleryPage({ isVisible = true }: { isVisible?: boolean }): React.JSX.Element {
  const { accessToken, refreshSession } = useAuth();
  const [images, setImages] = useState<GalleryImage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedImage, setSelectedImage] = useState<GalleryImage | null>(null);

  const fetchGallery = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      let token = accessToken;
      try {
        const data = await fetchGalleryImages(token);
        setImages(data.images);
      } catch (err) {
        if (err instanceof Error && err.message.includes('401')) {
          token = await refreshSession();
          if (!token) return;
          const data = await fetchGalleryImages(token);
          setImages(data.images);
        } else {
          throw err;
        }
      }
    } catch {
      setError('Unable to reach the server. Please check your connection.');
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, refreshSession]);

  useEffect(() => {
    void fetchGallery();
  }, [fetchGallery]);

  useEffect(() => {
    if (isVisible) {
      void fetchGallery();
    }
  }, [isVisible, fetchGallery]);

  if (isLoading) {
    return (
      <Box textAlign="center" padding={{ top: 'xxl' }}>
        <Spinner size="large" />
        <Box variant="p" color="text-body-secondary" margin={{ top: 's' }}>
          Loading gallery...
        </Box>
      </Box>
    );
  }

  return (
    <SpaceBetween size="l">
      {error && (
        <Alert
          type="error"
          dismissible
          onDismiss={() => setError(null)}
          action={<Button onClick={() => void fetchGallery()}>Retry</Button>}
        >
          {error}
        </Alert>
      )}

      <Cards
        cardDefinition={{
          header: (item) => (
            <Box fontSize="body-s" color="text-body-secondary">
              {formatDate(item.timestamp)}
            </Box>
          ),
          sections: [
            {
              id: 'thumbnail',
              content: (item) => (
                <div
                  role="button"
                  tabIndex={0}
                  style={{ cursor: 'pointer' }}
                  onClick={() => setSelectedImage(item)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setSelectedImage(item);
                    }
                  }}
                >
                  <img
                    src={item.thumbnail_url}
                    alt={item.prompt}
                    style={{
                      width: '100%',
                      height: '200px',
                      objectFit: 'cover',
                      borderRadius: '8px',
                    }}
                  />
                </div>
              ),
            },
            {
              id: 'prompt',
              content: (item) => (
                <Box variant="p" fontSize="body-s">
                  {item.prompt}
                </Box>
              ),
            },
          ],
        }}
        cardsPerRow={[{ cards: 1 }, { minWidth: 400, cards: 2 }, { minWidth: 800, cards: 3 }]}
        items={images}
        loading={isLoading}
        loadingText="Loading gallery images..."
        header={
          <Header
            variant="h1"
            counter={`(${images.length})`}
            actions={<Button iconName="refresh" onClick={() => void fetchGallery()} />}
          >
            🎨 Art Gallery
          </Header>
        }
        empty={
          <Box textAlign="center" padding="xxl" color="text-body-secondary">
            <SpaceBetween size="s">
              <Box variant="h3" fontWeight="bold">
                No images yet
              </Box>
              <Box variant="p">
                Use the Chat page to generate Australian wildlife and nature images. Try asking:
                &quot;Generate a koala in a eucalyptus forest&quot;
              </Box>
            </SpaceBetween>
          </Box>
        }
      />

      {selectedImage && (
        <Modal
          visible={true}
          onDismiss={() => setSelectedImage(null)}
          header={selectedImage.prompt}
          size="large"
        >
          <SpaceBetween size="s">
            <img
              src={selectedImage.full_url}
              alt={selectedImage.prompt}
              style={{ width: '100%', borderRadius: '8px' }}
            />
            <Box variant="p" color="text-body-secondary">
              Generated on {formatDate(selectedImage.timestamp)}
            </Box>
          </SpaceBetween>
        </Modal>
      )}
    </SpaceBetween>
  );
}

export default GalleryPage;
