// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import React from 'react';
import { describe, it, expect, vi, beforeAll } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

import { MessageList } from '../../frontend/src/chat/MessageList';
import { MessageInput } from '../../frontend/src/chat/MessageInput';
import { sanitizeError } from '../../frontend/src/api/agent';
import type { ChatMessage } from '../../frontend/src/types';

// jsdom doesn't implement scrollIntoView
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

function makeMessage(overrides: Partial<ChatMessage> & { role: 'user' | 'agent' }): ChatMessage {
  return {
    id: crypto.randomUUID(),
    content: 'Test message',
    timestamp: new Date(),
    ...overrides,
  };
}

// ---- MessageList Tests ----
describe('MessageList', () => {
  it('renders user messages with "You" label', () => {
    const messages = [makeMessage({ role: 'user', content: 'Hello from user' })];
    render(<MessageList messages={messages} isLoading={false} />);
    expect(screen.getByText('You')).toBeInTheDocument();
    expect(screen.getByText('Hello from user')).toBeInTheDocument();
  });

  it('renders agent messages with "Bush Ranger AI" label', () => {
    const messages = [makeMessage({ role: 'agent', content: 'Hello from agent' })];
    render(<MessageList messages={messages} isLoading={false} />);
    expect(screen.getByText('Bush Ranger AI')).toBeInTheDocument();
    expect(screen.getByText('Hello from agent')).toBeInTheDocument();
  });

  it('shows empty state when no messages and not loading', () => {
    render(<MessageList messages={[]} isLoading={false} />);
    expect(
      screen.getByText('Send a message to start chatting with Bush Ranger AI.'),
    ).toBeInTheDocument();
  });

  it('shows loading indicator when isLoading is true', () => {
    render(<MessageList messages={[]} isLoading={true} />);
    expect(screen.getByText('Bush Ranger AI is thinking...')).toBeInTheDocument();
  });

  it('renders both user and agent messages with correct labels', () => {
    const messages = [
      makeMessage({ role: 'user', content: 'User question' }),
      makeMessage({ role: 'agent', content: 'Agent answer' }),
    ];
    render(<MessageList messages={messages} isLoading={false} />);
    expect(screen.getByText('You')).toBeInTheDocument();
    expect(screen.getByText('Bush Ranger AI')).toBeInTheDocument();
    expect(screen.getByText('User question')).toBeInTheDocument();
    expect(screen.getByText('Agent answer')).toBeInTheDocument();
  });
});

// ---- MessageInput Tests ----
describe('MessageInput', () => {
  it('calls onSend when button clicked with non-empty input', () => {
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} isLoading={false} error={null} />);

    const input = screen.getByPlaceholderText('Ask Bush Ranger AI a question...');
    fireEvent.change(input, { target: { value: 'Hello' } });
    // Cloudscape Input uses a custom onChange, so we need to fire the native input event
    // Actually, Cloudscape wraps native input, so fireEvent.input should work
    fireEvent.input(input, { target: { value: 'Hello' } });

    const button = screen.getByText('Send');
    fireEvent.click(button);

    expect(onSend).toHaveBeenCalledWith('Hello');
  });

  it('disables input and button when isLoading is true', () => {
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} isLoading={true} error={null} />);

    const input = screen.getByPlaceholderText('Ask Bush Ranger AI a question...');
    expect(input).toBeDisabled();

    // Cloudscape Button renders a <button> wrapping a <span> with the text.
    // getByText('Send') returns the <span>, so we find the closest <button>.
    const buttonSpan = screen.getByText('Send');
    const button = buttonSpan.closest('button')!;
    expect(button).toBeDisabled();
  });

  it('shows error message when error prop is set', () => {
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} isLoading={false} error="Something went wrong" />);

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('does not show error when error is null', () => {
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} isLoading={false} error={null} />);

    expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument();
  });

  it('does not call onSend when input is empty', () => {
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} isLoading={false} error={null} />);

    const button = screen.getByText('Send');
    fireEvent.click(button);

    expect(onSend).not.toHaveBeenCalled();
  });
});

// ---- sanitizeError Tests ----
describe('sanitizeError', () => {
  it('strips AWS ARNs from error messages', () => {
    const result = sanitizeError(
      'Error accessing arn:aws:dynamodb:us-east-1:123456789:table/MyTable',
    );
    expect(result).not.toContain('arn:aws');
  });

  it('strips stack traces from error messages', () => {
    const result = sanitizeError('Failed at Object.handler (index.js:42:10)');
    expect(result).not.toContain('index.js:42:10');
  });

  it('strips exception names from error messages', () => {
    const result = sanitizeError('ResourceNotFoundException: Table not found');
    expect(result).not.toContain('ResourceNotFoundException');
  });

  it('returns fallback message for empty sanitized result', () => {
    const result = sanitizeError('arn:aws:s3:::my-bucket/key');
    expect(result).toBe('Something went wrong. Please try again.');
  });

  it('preserves safe user-facing text', () => {
    const result = sanitizeError('Please check your connection and try again.');
    expect(result).toBe('Please check your connection and try again.');
  });

  it('strips internal amazonaws.com URLs', () => {
    const result = sanitizeError(
      'Failed to connect to https://dynamodb.us-east-1.amazonaws.com/table',
    );
    expect(result).not.toContain('amazonaws.com');
  });
});
