// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import React, { useState, useCallback, useEffect, useRef } from 'react';
import Container from '@cloudscape-design/components/container';
import Header from '@cloudscape-design/components/header';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Box from '@cloudscape-design/components/box';
import ColumnLayout from '@cloudscape-design/components/column-layout';
import StatusIndicator from '@cloudscape-design/components/status-indicator';
import ExpandableSection from '@cloudscape-design/components/expandable-section';
import Markdown from 'react-markdown';
import { MessageInput } from './MessageInput';
import { Suggestions } from './Suggestions';
import { invokeAgent } from '../api/agent';
import { useAuth } from '../auth/AuthProvider';

interface QueryRecord {
  id: string;
  question: string;
  answer: string;
  timestamp: Date;
}

/**
 * Extract the actor ID (sub claim) from a JWT access token.
 * Returns undefined if the token is null, malformed, or missing the sub claim.
 */
export function extractActorId(token: string | null): string | undefined {
  if (!token) return undefined;
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.sub;
  } catch {
    return undefined;
  }
}

export function ChatPage(): React.JSX.Element {
  const { accessToken, refreshSession, isAuthenticated } = useAuth();
  const [sessionId, setSessionId] = useState<string>(() => crypto.randomUUID());
  const prevAuthRef = useRef(isAuthenticated);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [currentAnswer, setCurrentAnswer] = useState<string>('');
  const [currentQuestion, setCurrentQuestion] = useState<string>('');
  const [history, setHistory] = useState<QueryRecord[]>([]);

  useEffect(() => {
    const wasAuthenticated = prevAuthRef.current;
    prevAuthRef.current = isAuthenticated;

    // Reset sessionId on sign-out (was authenticated, now not) or sign-in (was not, now is)
    if (wasAuthenticated !== isAuthenticated) {
      setSessionId(crypto.randomUUID());
    }
  }, [isAuthenticated]);

  useEffect(() => {
    navigator.geolocation?.getCurrentPosition(
      (pos) => setUserLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => {},
      { timeout: 5000 },
    );
  }, []);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isLoading) return;
      setError(null);
      setCurrentQuestion(content.trim());
      setCurrentAnswer('');
      setIsLoading(true);

      try {
        let token = accessToken;
        const actorId = extractActorId(token);
        let response = await invokeAgent(content.trim(), token, userLocation, sessionId, actorId);

        if (response.status === 401) {
          token = await refreshSession();
          if (!token) return;
          const refreshedActorId = extractActorId(token);
          response = await invokeAgent(
            content.trim(),
            token,
            userLocation,
            sessionId,
            refreshedActorId,
          );
        }

        if (!response.ok) {
          setError('Something went wrong. Please try again.');
          return;
        }

        const data = await response.json();
        let agentText = data.response ?? '';
        try {
          const parsed = JSON.parse(agentText);
          if (parsed.result) agentText = parsed.result;
        } catch {
          // Not JSON
        }

        setCurrentAnswer(agentText);
        setHistory((prev) => [
          {
            id: crypto.randomUUID(),
            question: content.trim(),
            answer: agentText,
            timestamp: new Date(),
          },
          ...prev,
        ]);
      } catch {
        setError('Unable to reach the server. Please check your connection and try again.');
      } finally {
        setIsLoading(false);
      }
    },
    [accessToken, isLoading, refreshSession, sessionId, userLocation],
  );

  return (
    <SpaceBetween size="l">
      {/* Input bar */}
      <Container header={<Header variant="h1">🌿 Bush Ranger AI</Header>}>
        <MessageInput onSend={(msg) => void sendMessage(msg)} isLoading={isLoading} error={error} />
      </Container>

      {/* Suggestions */}
      <Suggestions onSelect={(msg) => void sendMessage(msg)} />

      {/* Main response area */}
      <ColumnLayout columns={history.length > 0 ? 2 : 1} variant="text-grid">
        <Container
          header={
            <Header variant="h2">
              {isLoading ? 'Thinking...' : currentQuestion || 'Response'}
            </Header>
          }
        >
          {isLoading && (
            <Box padding="l">
              <Box variant="p" color="text-body-secondary" margin={{ bottom: 's' }}>
                <strong>You:</strong> {currentQuestion}
              </Box>
              <Box textAlign="center">
                <StatusIndicator type="loading">Bush Ranger AI is thinking...</StatusIndicator>
              </Box>
            </Box>
          )}
          {!isLoading && !currentAnswer && (
            <Box padding="l">
              <SpaceBetween size="m">
                <Box variant="h3" textAlign="center">
                  Welcome to Bush Ranger AI
                </Box>
                <Box variant="p" color="text-body-secondary" textAlign="center">
                  Your Australian park ranger assistant. Here&apos;s what I can help with:
                </Box>
                <ColumnLayout columns={2} variant="text-grid">
                  <div>
                    <Box variant="h4">🦘 Wildlife Tracking</Box>
                    <Box variant="p" fontSize="body-s" color="text-body-secondary">
                      Log sightings, search by species, location, or conservation status
                    </Box>
                  </div>
                  <div>
                    <Box variant="h4">📄 Conservation Docs</Box>
                    <Box variant="p" fontSize="body-s" color="text-body-secondary">
                      Search fact sheets, management plans, and emergency procedures
                    </Box>
                  </div>
                  <div>
                    <Box variant="h4">🌤️ Weather &amp; Fire Danger</Box>
                    <Box variant="p" fontSize="body-s" color="text-body-secondary">
                      Current conditions, forecasts, and fire danger assessments
                    </Box>
                  </div>
                  <div>
                    <Box variant="h4">🎨 AI Image Generation</Box>
                    <Box variant="p" fontSize="body-s" color="text-body-secondary">
                      Generate images of Australian wildlife and nature for reports and displays
                    </Box>
                  </div>
                </ColumnLayout>
                <Box variant="p" color="text-body-secondary" textAlign="center" fontSize="body-s">
                  Try a quick action below, or type your own question.
                </Box>
              </SpaceBetween>
            </Box>
          )}
          {!isLoading && currentAnswer && (
            <div style={{ lineHeight: 1.6 }}>
              <Markdown>{currentAnswer}</Markdown>
            </div>
          )}
        </Container>

        {history.length > 0 && (
          <Container header={<Header variant="h2">History</Header>}>
            <SpaceBetween size="s">
              {history.map((record) => (
                <ExpandableSection key={record.id} headerText={record.question} variant="footer">
                  <div style={{ lineHeight: 1.6 }}>
                    <Markdown>{record.answer}</Markdown>
                  </div>
                </ExpandableSection>
              ))}
            </SpaceBetween>
          </Container>
        )}
      </ColumnLayout>
    </SpaceBetween>
  );
}
