// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import React from 'react';
import Button from '@cloudscape-design/components/button';
import Box from '@cloudscape-design/components/box';
import SpaceBetween from '@cloudscape-design/components/space-between';

interface SuggestionsProps {
  onSelect: (message: string) => void;
}

const SUGGESTIONS = [
  { id: 'nearby', emoji: '📍', text: "What's nearby?", message: "What's nearby?" },
  { id: 'briefing', emoji: '☀️', text: 'Morning briefing', message: 'Give me my morning briefing.' },
  { id: 'weather', emoji: '🌤️', text: 'Check weather', message: 'What is the current weather for my area?' },
  { id: 'sighting', emoji: '🦘', text: 'Log sighting', message: 'I want to log a wildlife sighting.' },
  { id: 'fire', emoji: '🔥', text: 'Fire danger', message: 'What is the current fire danger rating for my area?' },
  { id: 'species', emoji: '🐨', text: 'Species info', message: 'Tell me about koala conservation status.' },
  { id: 'docs', emoji: '📄', text: 'Search documents', message: 'Search conservation documents for bushfire response procedures.' },
];

export function Suggestions({ onSelect }: SuggestionsProps): React.JSX.Element {
  return (
    <div className="bush-ranger-suggestions">
      <Box padding="s">
        <Box variant="h4" padding={{ bottom: 'xs' }}>Quick Action Examples</Box>
        <SpaceBetween direction="horizontal" size="xs">
          {SUGGESTIONS.map((s) => (
            <Button key={s.id} onClick={() => onSelect(s.message)}>
              {s.emoji} {s.text}
            </Button>
          ))}
        </SpaceBetween>
      </Box>
    </div>
  );
}
