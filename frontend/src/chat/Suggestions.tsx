// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import React from 'react';
import ButtonGroup from '@cloudscape-design/components/button-group';
import Box from '@cloudscape-design/components/box';

interface SuggestionsProps {
  onSelect: (message: string) => void;
}

const SUGGESTIONS = [
  {
    id: 'weather',
    text: 'Check weather',
    message: 'What is the current weather at Kakadu National Park?',
  },
  { id: 'sighting', text: 'Log sighting', message: 'I want to log a wildlife sighting.' },
  {
    id: 'fire',
    text: 'Fire danger',
    message: 'What is the current fire danger rating for my area?',
  },
  { id: 'species', text: 'Species info', message: 'Tell me about koala conservation status.' },
  {
    id: 'docs',
    text: 'Search documents',
    message: 'Search conservation documents for bushfire response procedures.',
  },
];

export function Suggestions({ onSelect }: SuggestionsProps): React.JSX.Element {
  return (
    <Box padding="s">
      <Box variant="h4" padding={{ bottom: 'xs' }}>
        Quick actions
      </Box>
      <ButtonGroup
        variant="icon"
        onItemClick={({ detail }) => {
          const suggestion = SUGGESTIONS.find((s) => s.id === detail.id);
          if (suggestion) {
            onSelect(suggestion.message);
          }
        }}
        items={SUGGESTIONS.map((s) => ({
          type: 'icon-button' as const,
          id: s.id,
          text: s.text,
          iconName: 'status-info' as const,
        }))}
      />
    </Box>
  );
}
