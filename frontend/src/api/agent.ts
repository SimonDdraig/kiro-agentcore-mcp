// Copyright 2025 Bush Ranger AI Project. All rights reserved.

const API_ENDPOINT = import.meta.env.VITE_API_ENDPOINT ?? '';
const REQUEST_TIMEOUT_MS = 30_000;

/**
 * Sanitize error messages to prevent exposing internal details.
 * Strips stack traces, ARNs, internal URLs, and exception class names.
 */
function sanitizeError(message: string): string {
  const internalPatterns = [
    /arn:aws:[^\s]+/gi,
    /https?:\/\/[^\s]*\.internal[^\s]*/gi,
    /https?:\/\/[^\s]*\.amazonaws\.com[^\s]*/gi,
    /at\s+[\w$.]+\s*\(.*:\d+:\d+\)/g,
    /\b\w+Exception\b/g,
    /\b\w+Error:\s/g,
    /Traceback\s*\(most recent call last\)/gi,
    /File\s+"[^"]+",\s+line\s+\d+/g,
  ];

  let sanitized = message;
  for (const pattern of internalPatterns) {
    sanitized = sanitized.replace(pattern, '');
  }

  sanitized = sanitized.trim();
  return sanitized || 'Something went wrong. Please try again.';
}

/**
 * Invoke the Bush Ranger AI agent via the HTTP API Gateway.
 * Sends a POST request to /invoke with the user's message and Bearer token.
 * Enforces a 30-second timeout.
 */
export async function invokeAgent(message: string, accessToken: string | null): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_ENDPOINT}/invoke`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: JSON.stringify({ message }),
      signal: controller.signal,
    });

    return response;
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      return new Response(JSON.stringify({ error: 'Request timed out. Please try again.' }), {
        status: 408,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    return new Response(
      JSON.stringify({ error: 'Unable to reach the server. Please check your connection.' }),
      { status: 0, headers: { 'Content-Type': 'application/json' } },
    );
  } finally {
    clearTimeout(timeoutId);
  }
}

export { sanitizeError };
