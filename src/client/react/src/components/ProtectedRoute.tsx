/**
 * ProtectedRoute.tsx
 * Restricts access to routes based on authentication state.
 * - Shows a loader while authentication is being determined.
 * - Redirects unauthenticated users to the login page, preserving the intended destination.
 */

import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import FullPageLoader from './FullPageLoader';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

/**
 * ProtectedRoute
 * Wraps children and only renders them if the user is authenticated.
 * - Shows FullPageLoader while loading.
 * - Redirects to /login if not authenticated, passing the current location for post-login redirect.
 */
const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <FullPageLoader />;
  }

  if (!isAuthenticated) {
    // Redirect to login page with return url
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
};

export default ProtectedRoute;
