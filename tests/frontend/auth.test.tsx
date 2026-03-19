// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

// Mock amazon-cognito-identity-js BEFORE any imports that use it
// Use resolved path since test files are outside frontend/
vi.mock('amazon-cognito-identity-js', () => ({
  CognitoUserPool: vi.fn().mockImplementation(() => ({
    getCurrentUser: vi.fn().mockReturnValue(null),
  })),
  CognitoUser: vi.fn(),
  CognitoUserSession: vi.fn(),
  AuthenticationDetails: vi.fn(),
}));

import { AuthProvider, useAuth } from '../../frontend/src/auth/AuthProvider';
import { SignIn } from '../../frontend/src/auth/SignIn';

// ---- AuthProvider Tests ----
describe('AuthProvider', () => {
  it('provides auth context to children', () => {
    function TestChild() {
      const auth = useAuth();
      return <div data-testid="auth-status">{auth.isAuthenticated ? 'yes' : 'no'}</div>;
    }

    render(
      <AuthProvider>
        <TestChild />
      </AuthProvider>,
    );

    expect(screen.getByTestId('auth-status')).toHaveTextContent('no');
  });

  it('useAuth throws when used outside AuthProvider', () => {
    function BadChild() {
      useAuth();
      return <div>Should not render</div>;
    }

    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<BadChild />)).toThrow('useAuth must be used within an AuthProvider');
    consoleSpy.mockRestore();
  });
});

// ---- SignIn Tests ----
describe('SignIn', () => {
  it('renders email and password fields', () => {
    render(
      <AuthProvider>
        <SignIn />
      </AuthProvider>,
    );

    expect(screen.getByText('Email')).toBeInTheDocument();
    expect(screen.getByText('Password')).toBeInTheDocument();
  });

  it('renders the sign-in button', () => {
    render(
      <AuthProvider>
        <SignIn />
      </AuthProvider>,
    );

    expect(screen.getByText('Sign in')).toBeInTheDocument();
  });

  it('renders the Bush Ranger AI header', () => {
    render(
      <AuthProvider>
        <SignIn />
      </AuthProvider>,
    );

    expect(screen.getByText('Bush Ranger AI')).toBeInTheDocument();
  });

  it('renders email input with correct placeholder', () => {
    render(
      <AuthProvider>
        <SignIn />
      </AuthProvider>,
    );

    expect(screen.getByPlaceholderText('ranger@example.com')).toBeInTheDocument();
  });

  it('renders password input with correct placeholder', () => {
    render(
      <AuthProvider>
        <SignIn />
      </AuthProvider>,
    );

    expect(screen.getByPlaceholderText('Enter your password')).toBeInTheDocument();
  });
});
