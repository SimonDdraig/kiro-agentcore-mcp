// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import React from 'react';
import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest';
import { render } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import * as fc from 'fast-check';

import { MessageList } from '../../frontend/src/chat/MessageList';
import { sanitizeError, invokeAgent } from '../../frontend/src/api/agent';
import type { ChatMessage } from '../../frontend/src/types';

// jsdom doesn't implement scrollIntoView
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

// ---- Arbitrary generators ----

const chatMessageArb = (role: 'user' | 'agent'): fc.Arbitrary<ChatMessage> =>
  fc.record({
    id: fc.uuid(),
    role: fc.constant(role),
    content: fc.string({ minLength: 1, maxLength: 200 }),
    timestamp: fc.date(),
  });

const mixedMessagesArb: fc.Arbitrary<ChatMessage[]> = fc.array(
  fc.oneof(chatMessageArb('user'), chatMessageArb('agent')),
  { minLength: 1, maxLength: 20 },
);

// Helper: build a string from an array of characters
const stringFromChars = (
  chars: string[],
  opts: { minLength: number; maxLength: number },
): fc.Arbitrary<string> =>
  fc.array(fc.constantFrom(...chars), opts).map((arr) => arr.join(''));

// ---- Property 13: Chat Message Role Distinction ----
describe('Feature: aws-agentcore-mcp-infrastructure, Property 13: Chat message role distinction', () => {
  it('For any list of ChatMessages with mixed roles, MessageList renders every message with correct role label', () => {
    /**
     * Validates: Requirements 11.3, 11.4
     */
    fc.assert(
      fc.property(mixedMessagesArb, (messages) => {
        const { container, unmount } = render(
          <MessageList messages={messages} isLoading={false} />,
        );

        const userCount = messages.filter((m) => m.role === 'user').length;
        const agentCount = messages.filter((m) => m.role === 'agent').length;

        // Verify role distinction via data-role attributes
        const userBoxes = container.querySelectorAll('[data-role="user"]');
        const agentBoxes = container.querySelectorAll('[data-role="agent"]');

        expect(userBoxes.length).toBe(userCount);
        expect(agentBoxes.length).toBe(agentCount);

        // Verify total message count matches
        expect(userBoxes.length + agentBoxes.length).toBe(messages.length);

        // Verify user messages show "You" label and agent messages show "Bush Ranger AI"
        userBoxes.forEach((box) => {
          expect(box.textContent).toContain('You');
        });
        agentBoxes.forEach((box) => {
          expect(box.textContent).toContain('Bush Ranger AI');
        });

        unmount();
      }),
      { numRuns: 100 },
    );
  });
});

// ---- Property 14: Error Messages Don't Expose Internals ----
describe('Feature: aws-agentcore-mcp-infrastructure, Property 14: Error messages don\'t expose internals', () => {
  const arnArb = fc
    .tuple(
      fc.constantFrom('dynamodb', 's3', 'lambda', 'iam', 'sqs', 'sns'),
      fc.constantFrom('us-east-1', 'ap-southeast-2', 'eu-west-1'),
      fc.stringMatching(/^[0-9]{12}$/),
      stringFromChars(['a', 'b', 'c', 'd', 'e', 'f', '1', '2', '3', '-', '/'], { minLength: 1, maxLength: 30 }),
    )
    .map(
      ([service, region, account, resource]) =>
        `arn:aws:${service}:${region}:${account}:${resource}`,
    );

  // Generate stack traces matching sanitizeError regex: at [\w$.]+\s*\(.*:\d+:\d+\)
  const stackTraceArb = fc
    .tuple(
      stringFromChars(['a', 'b', 'c', 'A', 'B', 'C', '$', '.', '_', '0', '1'], { minLength: 1, maxLength: 20 }),
      stringFromChars(['a', 'b', 'c', 'd', 'e', '/', '.', '_'], { minLength: 1, maxLength: 20 }),
      fc.nat({ max: 999 }),
      fc.nat({ max: 99 }),
    )
    .map(([obj, file, line, col]) => `at ${obj} (${file}:${line}:${col})`);

  const internalUrlArb = fc
    .tuple(
      fc.constantFrom('dynamodb', 's3', 'lambda', 'sqs'),
      fc.constantFrom('us-east-1', 'ap-southeast-2'),
    )
    .map(
      ([service, region]) =>
        `https://${service}.${region}.amazonaws.com/some-resource`,
    );

  const exceptionNameArb = fc.constantFrom(
    'ResourceNotFoundException',
    'ValidationException',
    'AccessDeniedException',
    'ThrottlingException',
    'InternalServerException',
  );

  it('For any error string containing ARNs, sanitizeError strips them', () => {
    /**
     * Validates: Requirements 11.7
     */
    fc.assert(
      fc.property(arnArb, fc.string({ maxLength: 50 }), (arn, prefix) => {
        const input = `${prefix} ${arn} occurred`;
        const result = sanitizeError(input);
        expect(result).not.toContain('arn:aws:');
      }),
      { numRuns: 100 },
    );
  });

  it('For any error string containing stack traces, sanitizeError strips them', () => {
    /**
     * Validates: Requirements 11.7
     */
    fc.assert(
      fc.property(stackTraceArb, fc.string({ maxLength: 50 }), (trace, prefix) => {
        const input = `${prefix} ${trace}`;
        const result = sanitizeError(input);
        expect(result).not.toMatch(/at\s+[\w$.]+\s*\(.*:\d+:\d+\)/);
      }),
      { numRuns: 100 },
    );
  });

  it('For any error string containing internal URLs, sanitizeError strips them', () => {
    /**
     * Validates: Requirements 11.7
     */
    fc.assert(
      fc.property(internalUrlArb, fc.string({ maxLength: 50 }), (url, prefix) => {
        const input = `${prefix} ${url}`;
        const result = sanitizeError(input);
        expect(result).not.toContain('amazonaws.com');
      }),
      { numRuns: 100 },
    );
  });

  it('For any error string containing exception names, sanitizeError strips them', () => {
    /**
     * Validates: Requirements 11.7
     */
    fc.assert(
      fc.property(exceptionNameArb, fc.string({ maxLength: 50 }), (exception, prefix) => {
        const input = `${prefix} ${exception}`;
        const result = sanitizeError(input);
        expect(result).not.toContain(exception);
      }),
      { numRuns: 100 },
    );
  });
});

// ---- Property 15: API Requests Include Auth Token ----
describe('Feature: aws-agentcore-mcp-infrastructure, Property 15: API requests include auth token', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ response: 'ok', requestId: '123' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('For any API call with a token, the request includes Authorization: Bearer {token}', async () => {
    /**
     * Validates: Requirements 13.5
     */
    await fc.assert(
      fc.asyncProperty(
        stringFromChars(
          'abcdefghijklmnopqrstuvwxyz0123456789.-_'.split(''),
          { minLength: 10, maxLength: 200 },
        ),
        stringFromChars('abcde ?!'.split(''), { minLength: 1, maxLength: 100 }),
        async (token, message) => {
          await invokeAgent(message, token);

          const mockFetch = globalThis.fetch as ReturnType<typeof vi.fn>;
          expect(mockFetch).toHaveBeenCalledTimes(1);

          const [, options] = mockFetch.mock.calls[0] as [string, RequestInit];
          const headers = options.headers as Record<string, string>;
          expect(headers['Authorization']).toBe(`Bearer ${token}`);

          mockFetch.mockClear();
        },
      ),
      { numRuns: 100 },
    );
  });
});

// ---- Property 17: Unauthenticated Requests Rejected ----
describe('Feature: aws-agentcore-mcp-infrastructure, Property 17: Unauthenticated requests rejected', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ response: 'ok', requestId: '123' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('For any request with null token, no Authorization header is sent', async () => {
    /**
     * Validates: Requirements 14.3
     */
    await fc.assert(
      fc.asyncProperty(
        stringFromChars('abcde ?!'.split(''), { minLength: 1, maxLength: 100 }),
        async (message) => {
          await invokeAgent(message, null);

          const mockFetch = globalThis.fetch as ReturnType<typeof vi.fn>;
          expect(mockFetch).toHaveBeenCalledTimes(1);

          const [, options] = mockFetch.mock.calls[0] as [string, RequestInit];
          const headers = options.headers as Record<string, string>;
          expect(headers).not.toHaveProperty('Authorization');

          mockFetch.mockClear();
        },
      ),
      { numRuns: 100 },
    );
  });
});
