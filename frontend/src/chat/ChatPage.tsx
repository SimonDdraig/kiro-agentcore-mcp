// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import React, { useState, useCallback } from 'react';
import ContentLayout from '@cloudscape-design/components/content-layout';
import Container from '@cloudscape-design/components/container';
import Header from '@cloudscape-design/components/header';
import SpaceBetween from '@cloudscape-design/components/space-between';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { Suggestions } from './Suggestions';
import { invokeAgent } from '../api/agent';
import { useAuth } from '../auth/AuthProvider';
import type { ChatMessage } from '../types';

export function ChatPage(): React.JSX.Element {
  const { accessToken, refreshSession } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isLoading) return;

      setError(null);

      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'user',
        content: content.trim(),
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);

      try {
        let token = accessToken;
        let response = await invokeAgent(content.trim(), token);

        if (response.status === 401) {
          token = await refreshSession();
          if (!token) return;
          response = await invokeAgent(content.trim(), token);
        }

        if (!response.ok) {
          setError('Something went wrong. Please try again.');
          return;
        }

        const data = await response.json();

        const agentMessage: ChatMessage = {
          id: crypto.randomUUID(),
          role: 'agent',
          content: data.response,
          timestamp: new Date(),
        };

        setMessages((prev) => [...prev, agentMessage]);
      } catch {
        setError('Unable to reach the server. Please check your connection and try again.');
      } finally {
        setIsLoading(false);
      }
    },
    [accessToken, isLoading, refreshSession],
  );

  return (
    <ContentLayout header={<Header variant="h1">Chat with Bush Ranger AI</Header>}>
      <SpaceBetween size="l">
        <Container>
          <SpaceBetween size="m">
            <MessageList messages={messages} isLoading={isLoading} />
            <MessageInput
              onSend={(msg) => void sendMessage(msg)}
              isLoading={isLoading}
              error={error}
            />
          </SpaceBetween>
        </Container>
        <Suggestions onSelect={(msg) => void sendMessage(msg)} />
      </SpaceBetween>
    </ContentLayout>
  );
}
