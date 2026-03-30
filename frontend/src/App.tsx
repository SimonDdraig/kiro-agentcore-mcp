// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import React, { useEffect, useState } from 'react';
import AppLayout from '@cloudscape-design/components/app-layout';
import TopNavigation from '@cloudscape-design/components/top-navigation';
import Spinner from '@cloudscape-design/components/spinner';
import '@cloudscape-design/global-styles/index.css';
import './bush-theme.css';
import { AuthProvider, useAuth } from './auth/AuthProvider';
import { SignIn } from './auth/SignIn';
import { ChatPage } from './chat/ChatPage';

const BG_IMAGES = ['/outback-bg-1.png', '/outback-bg-2.png', '/outback-bg-3.png', '/outback-bg-4.png'];
const BG_INTERVAL_MS = 60_000;

function BackgroundRotator(): React.JSX.Element {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setIndex((i) => (i + 1) % BG_IMAGES.length), BG_INTERVAL_MS);
    return () => clearInterval(timer);
  }, []);

  return (
    <>
      {BG_IMAGES.map((src, i) => (
        <div
          key={src}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: -1,
            backgroundImage: `url(${src})`,
            backgroundSize: 'cover',
            backgroundPosition: 'center bottom',
            backgroundRepeat: 'no-repeat',
            opacity: i === index ? 1 : 0,
            transition: 'opacity 2s ease-in-out',
          }}
        />
      ))}
    </>
  );
}

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
          title: '🌿 Bush Ranger AI',
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
      <BackgroundRotator />
      <AppContent />
    </AuthProvider>
  );
}
