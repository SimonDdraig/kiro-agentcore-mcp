// Copyright 2025 Bush Ranger AI Project. All rights reserved.

export interface ChatMessage {
  id: string;
  role: 'user' | 'agent';
  content: string;
  timestamp: Date;
}

export interface InvokeRequest {
  message: string;
}

export interface InvokeResponse {
  response: string;
  requestId: string;
}
