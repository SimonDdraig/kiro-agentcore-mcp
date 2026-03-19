// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import React, { useState } from 'react';
import Input from '@cloudscape-design/components/input';
import Button from '@cloudscape-design/components/button';
import FormField from '@cloudscape-design/components/form-field';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Alert from '@cloudscape-design/components/alert';

interface MessageInputProps {
  onSend: (message: string) => void;
  isLoading: boolean;
  error: string | null;
}

export function MessageInput({ onSend, isLoading, error }: MessageInputProps): React.JSX.Element {
  const [value, setValue] = useState('');

  const handleSend = () => {
    if (value.trim() && !isLoading) {
      onSend(value.trim());
      setValue('');
    }
  };

  const handleKeyDown = (event: CustomEvent<{ keyCode: number; key: string }>) => {
    if (event.detail.key === 'Enter' && !isLoading) {
      handleSend();
    }
  };

  return (
    <SpaceBetween size="s">
      {error && <Alert type="error">{error}</Alert>}
      <FormField>
        <SpaceBetween direction="horizontal" size="xs">
          <div style={{ flex: 1 }}>
            <Input
              value={value}
              onChange={({ detail }) => setValue(detail.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask Bush Ranger AI a question..."
              disabled={isLoading}
            />
          </div>
          <Button
            variant="primary"
            onClick={handleSend}
            loading={isLoading}
            disabled={!value.trim()}
          >
            Send
          </Button>
        </SpaceBetween>
      </FormField>
    </SpaceBetween>
  );
}
