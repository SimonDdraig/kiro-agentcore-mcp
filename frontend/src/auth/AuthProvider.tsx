// Copyright 2025 Bush Ranger AI Project. All rights reserved.
import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import {
  CognitoUserPool,
  CognitoUser,
  CognitoUserSession,
  AuthenticationDetails,
} from 'amazon-cognito-identity-js';

const USER_POOL_ID = import.meta.env.VITE_COGNITO_USER_POOL_ID ?? '';
const CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID ?? '';

const userPool = new CognitoUserPool({
  UserPoolId: USER_POOL_ID,
  ClientId: CLIENT_ID,
});

interface AuthContextValue {
  isAuthenticated: boolean;
  isLoading: boolean;
  accessToken: string | null;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => void;
  refreshSession: () => Promise<string | null>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps): React.JSX.Element {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [accessToken, setAccessToken] = useState<string | null>(null);

  const getSession = useCallback((): Promise<CognitoUserSession | null> => {
    return new Promise((resolve) => {
      const currentUser = userPool.getCurrentUser();
      if (!currentUser) {
        resolve(null);
        return;
      }
      currentUser.getSession((err: Error | null, session: CognitoUserSession | null) => {
        if (err || !session || !session.isValid()) {
          resolve(null);
          return;
        }
        resolve(session);
      });
    });
  }, []);

  const refreshSession = useCallback(async (): Promise<string | null> => {
    const currentUser = userPool.getCurrentUser();
    if (!currentUser) {
      setIsAuthenticated(false);
      setAccessToken(null);
      return null;
    }

    return new Promise((resolve) => {
      currentUser.getSession((err: Error | null, session: CognitoUserSession | null) => {
        if (err || !session) {
          setIsAuthenticated(false);
          setAccessToken(null);
          resolve(null);
          return;
        }

        const refreshToken = session.getRefreshToken();
        currentUser.refreshSession(
          refreshToken,
          (refreshErr: Error | null, newSession: CognitoUserSession) => {
            if (refreshErr || !newSession) {
              setIsAuthenticated(false);
              setAccessToken(null);
              resolve(null);
              return;
            }
            const token = newSession.getAccessToken().getJwtToken();
            setAccessToken(token);
            setIsAuthenticated(true);
            resolve(token);
          },
        );
      });
    });
  }, []);

  useEffect(() => {
    const checkSession = async () => {
      const session = await getSession();
      if (session) {
        setAccessToken(session.getAccessToken().getJwtToken());
        setIsAuthenticated(true);
      }
      setIsLoading(false);
    };
    void checkSession();
  }, [getSession]);

  const signIn = useCallback(async (email: string, password: string): Promise<void> => {
    return new Promise((resolve, reject) => {
      const cognitoUser = new CognitoUser({
        Username: email,
        Pool: userPool,
      });

      const authDetails = new AuthenticationDetails({
        Username: email,
        Password: password,
      });

      cognitoUser.authenticateUser(authDetails, {
        onSuccess: (session: CognitoUserSession) => {
          const token = session.getAccessToken().getJwtToken();
          setAccessToken(token);
          setIsAuthenticated(true);
          resolve();
        },
        onFailure: (err: Error) => {
          reject(err);
        },
      });
    });
  }, []);

  const signOut = useCallback(() => {
    const currentUser = userPool.getCurrentUser();
    if (currentUser) {
      currentUser.signOut();
    }
    setAccessToken(null);
    setIsAuthenticated(false);
  }, []);

  const value: AuthContextValue = {
    isAuthenticated,
    isLoading,
    accessToken,
    signIn,
    signOut,
    refreshSession,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
