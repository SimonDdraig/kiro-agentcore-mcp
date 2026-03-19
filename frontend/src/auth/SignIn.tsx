// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import React, { useState } from 'react';
import Form from '@cloudscape-design/components/form';
import FormField from '@cloudscape-design/components/form-field';
import Input from '@cloudscape-design/components/input';
import Button from '@cloudscape-design/components/button';
import Container from '@cloudscape-design/components/container';
import Header from '@cloudscape-design/components/header';
import SpaceBetween from '@cloudscape-design/components/space-between';
import Alert from '@cloudscape-design/components/alert';
import { useAuth } from './AuthProvider';

export function SignIn(): React.JSX.Element {
  const { signIn } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await signIn(email, password);
    } catch (err) {
      if (err instanceof Error) {
        setError(
          err.message === 'Incorrect username or password.'
            ? 'Invalid username or password'
            : 'An error occurred during sign in. Please try again.',
        );
      } else {
        setError('An error occurred during sign in. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ maxWidth: 400, margin: '80px auto' }}>
      <Container header={<Header variant="h1">Bush Ranger AI</Header>}>
        <form onSubmit={(e) => void handleSubmit(e)}>
          <Form
            actions={
              <SpaceBetween direction="horizontal" size="xs">
                <Button variant="primary" loading={isSubmitting} formAction="submit">
                  Sign in
                </Button>
              </SpaceBetween>
            }
          >
            <SpaceBetween direction="vertical" size="l">
              {error && <Alert type="error">{error}</Alert>}
              <FormField label="Email">
                <Input
                  type="email"
                  value={email}
                  onChange={({ detail }) => setEmail(detail.value)}
                  placeholder="ranger@example.com"
                  disabled={isSubmitting}
                />
              </FormField>
              <FormField label="Password">
                <Input
                  type="password"
                  value={password}
                  onChange={({ detail }) => setPassword(detail.value)}
                  placeholder="Enter your password"
                  disabled={isSubmitting}
                />
              </FormField>
            </SpaceBetween>
          </Form>
        </form>
      </Container>
    </div>
  );
}
