import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import axios from 'axios';

// Utility function for authenticated API calls
export const makeAuthenticatedRequest = (token: string | null) => {
  return {
    get: (url: string, config = {}) => 
      axios.get(url, { 
        ...config, 
        headers: { ...config.headers, Authorization: `Bearer ${token}` } 
      }),
    post: (url: string, data: any, config = {}) => 
      axios.post(url, data, { 
        ...config, 
        headers: { ...config.headers, Authorization: `Bearer ${token}` } 
      }),
    put: (url: string, data: any, config = {}) => 
      axios.put(url, data, { 
        ...config, 
        headers: { ...config.headers, Authorization: `Bearer ${token}` } 
      }),
    delete: (url: string, config = {}) => 
      axios.delete(url, { 
        ...config, 
        headers: { ...config.headers, Authorization: `Bearer ${token}` } 
      })
  };
};

interface User {
  email: string;
  name: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (googleToken: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
  authRequest: ReturnType<typeof makeAuthenticatedRequest>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

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

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Check for existing token on mount
    const savedToken = localStorage.getItem('auth_token');
    if (savedToken) {
      setToken(savedToken);
      // Verify token and get user info
      verifyToken(savedToken);
    } else {
      // No token - user is not authenticated, stop loading
      setIsLoading(false);
    }
  }, []);

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

  const login = async (googleToken: string) => {
    try {
      setIsLoading(true);
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
    authRequest: makeAuthenticatedRequest(token)
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};