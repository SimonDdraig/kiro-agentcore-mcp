// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import React, { useEffect, useRef } from 'react';
import Box from '@cloudscape-design/components/box';
import SpaceBetween from '@cloudscape-design/components/space-between';
import StatusIndicator from '@cloudscape-design/components/status-indicator';
import type { ChatMessage } from '../types';

interface MessageListProps {
  messages: ChatMessage[];
  isLoading: boolean;
}

export function MessageList({ messages, isLoading }: MessageListProps): React.JSX.Element {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  if (messages.length === 0 && !isLoading) {
    return (
      <Box textAlign="center" color="text-body-secondary" padding="l">
        Send a message to start chatting with Bush Ranger AI.
      </Box>
    );
  }

  return (
    <div style={{ maxHeight: '60vh', overflowY: 'auto', padding: '8px 0' }}>
      <SpaceBetween size="m">
        {messages.map((message) => (
          <div
            key={message.id}
            style={{
              display: 'flex',
              justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start',
            }}
          >
            <Box
              padding="s"
              variant={message.role === 'user' ? 'awsui-key-label' : 'awsui-value-large'}
              data-role={message.role}
              color={message.role === 'user' ? 'text-status-info' : 'text-body-secondary'}
            >
              <SpaceBetween size="xxs">
                <Box fontWeight="bold" fontSize="body-s">
                  {message.role === 'user' ? 'You' : 'Bush Ranger AI'}
                </Box>
                <Box variant="p">{message.content}</Box>
              </SpaceBetween>
            </Box>
          </div>
        ))}
        {isLoading && (
          <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
            <Box padding="s">
              <StatusIndicator type="loading">Bush Ranger AI is thinking...</StatusIndicator>
            </Box>
          </div>
        )}
        <div ref={bottomRef} />
      </SpaceBetween>
    </div>
  );
}
