// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import React from 'react';
import AppLayout from '@cloudscape-design/components/app-layout';
import TopNavigation from '@cloudscape-design/components/top-navigation';
import Spinner from '@cloudscape-design/components/spinner';
import '@cloudscape-design/global-styles/index.css';
import { AuthProvider, useAuth } from './auth/AuthProvider';
import { SignIn } from './auth/SignIn';
import { ChatPage } from './chat/ChatPage';

function AppContent(): React.JSX.Element {
  const { isAuthenticated, isLoading, signOut } = useAuth();

  if (isLoading) {
    return (
      <div
        style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}
      >
        <Spinner size="large" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <SignIn />;
  }

  return (
    <>
      <TopNavigation
        identity={{
          href: '/',
          title: 'Bush Ranger AI',
        }}
        utilities={[
          {
            type: 'button',
            text: 'Sign out',
            onClick: signOut,
          },
        ]}
      />
      <AppLayout content={<ChatPage />} navigationHide toolsHide />
    </>
  );
}

export function App(): React.JSX.Element {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
