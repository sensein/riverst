/**
 * AuthContext.tsx
 * Provides authentication context and utilities for the React app.
 * Handles login, logout, token management, and authenticated API requests.
 */

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import axios from 'axios';

/**
 * Utility function for authenticated API calls.
 * Returns an object with get, post, put, and delete methods that include the Authorization header.
 */
const withAuthHeaders = (token: string | null, config: any = {}) => ({
  ...config,
  headers: { ...config.headers, Authorization: `Bearer ${token}` }
});

export const makeAuthenticatedRequest = (token: string | null) => ({
  get: (url: string, config = {}) => axios.get(url, withAuthHeaders(token, config)),
  post: (url: string, data: any, config = {}) => axios.post(url, data, withAuthHeaders(token, config)),
  put: (url: string, data: any, config = {}) => axios.put(url, data, withAuthHeaders(token, config)),
  delete: (url: string, config = {}) => axios.delete(url, withAuthHeaders(token, config))
});

/**
 * User information structure.
 */
interface User {
  email: string;
  name: string;
}

/**
 * AuthContextType
 * Describes the shape of the authentication context.
 */
interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (googleToken: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
  authRequest: ReturnType<typeof makeAuthenticatedRequest>;
  googleAuthEnabled: boolean;
}

/**
 * AuthContext
 * Provides authentication state and actions to the app.
 */
const AuthContext = createContext<AuthContextType | undefined>(undefined);

/**
 * useAuth
 * Custom hook to access authentication context.
 * Throws an error if used outside of AuthProvider.
 */
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

/**
 * AuthProvider
 * Wraps children with authentication context.
 * Handles token persistence, login, logout, and user state.
 */
export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [googleAuthEnabled, setGoogleAuthEnabled] = useState(false);

  useEffect(() => {
    // Check auth status and existing token on mount
    const initializeAuth = async () => {
      try {
        // Check if Google auth is enabled
        const statusResponse = await axios.get('/api/auth/status');
        setGoogleAuthEnabled(statusResponse.data.google_auth_enabled);

        if (!statusResponse.data.google_auth_enabled) {
          // If Google auth is disabled, automatically authenticate with bypass
          const bypassResponse = await axios.post('/api/auth/bypass');
          const { access_token, user: userData } = bypassResponse.data;

          setToken(access_token);
          setUser(userData);
          localStorage.setItem('auth_token', access_token);
          setIsLoading(false);
          return;
        }

        const savedToken = localStorage.getItem('auth_token');
        if (savedToken) {
          setToken(savedToken);
          // Verify token and get user info
          await verifyToken(savedToken);
        } else {
          // No token - user is not authenticated, stop loading
          setIsLoading(false);
        }
      } catch (error) {
        console.error('Failed to initialize auth:', error);
        setIsLoading(false);
      }
    };

    initializeAuth();
  }, []);

  /**
   * verifyToken
   * Verifies the token with the backend and fetches user info.
   */
  const verifyToken = async (authToken: string) => {
    try {
      const response = await axios.get('/api/auth/me', {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      setUser(response.data);
    } catch (error) {
      console.error('Token verification failed:', error);
      logout();
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * login
   * Authenticates the user with Google token.
   */
  const login = async (googleToken: string) => {
    try {
      setIsLoading(true);

      // Use Google authentication
      const response = await axios.post('/api/auth/google', {
        token: googleToken
      });

      const { access_token, user: userData } = response.data;

      setToken(access_token);
      setUser(userData);

      // Save token to localStorage
      localStorage.setItem('auth_token', access_token);

    } catch (error: any) {
      console.error('Login failed:', error);
      const errorMessage = error.response?.data?.detail || 'Login failed';
      throw new Error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * logout
   * Clears user and token from state and localStorage.
   */
  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem('auth_token');
  };

  const value: AuthContextType = {
    user,
    token,
    isLoading,
    login,
    logout,
    isAuthenticated: !!user && !!token,
    authRequest: makeAuthenticatedRequest(token),
    googleAuthEnabled
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};
