import { ConfigProvider } from 'antd';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Homepage from './pages/Homepage';
import { appTheme } from './theme';
import FullPageLoader from './components/FullPageLoader';
import ProtectedRoute from './components/ProtectedRoute';
import { AuthProvider } from './contexts/AuthContext';

import { Suspense, lazy } from 'react';

const AdvancedAvatarCreatorPage = lazy(() => import('./pages/AdvancedAvatarCreatorPage'));
const AvatarCreatorPage = lazy(() => import('./pages/AvatarCreatorPage'));
const AvatarInteraction = lazy(() => import('./pages/AvatarInteraction'));
const AvatarInteractionSettings = lazy(() => import('./pages/AvatarInteractionSettings'));
const SessionsList = lazy(() => import('./pages/SessionsList'));
const SessionDetail = lazy(() => import('./pages/SessionDetail'));
const LoginPage = lazy(() => import('./pages/LoginPage'));
const ErrorPage = lazy(() => import('./pages/ErrorPage'));

const AuthenticatedRoutes = () => (
  <AuthProvider>
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Homepage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/advanced-avatar-creation"
        element={
          <ProtectedRoute>
            <AdvancedAvatarCreatorPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/avatar-creation"
        element={
          <ProtectedRoute>
            <AvatarCreatorPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/avatar-interaction-settings"
        element={
          <ProtectedRoute>
            <AvatarInteractionSettings />
          </ProtectedRoute>
        }
      />
      <Route
        path="/sessions"
        element={
          <ProtectedRoute>
            <SessionsList />
          </ProtectedRoute>
        }
      />
      <Route
        path="/sessions/:id"
        element={
          <ProtectedRoute>
            <SessionDetail />
          </ProtectedRoute>
        }
      />
    </Routes>
  </AuthProvider>
);

const App = () => {
  return (
    <ConfigProvider theme={appTheme}>
      <Router>
        <Suspense fallback={<FullPageLoader />}>
          <Routes>
            {/* Completely unauthenticated routes - NO AuthProvider */}
            <Route path="/avatar-interaction/:sessionId" element={<AvatarInteraction />} />

            {/* All other routes - WITH AuthProvider (including login) */}
            <Route path="/*" element={<AuthenticatedRoutes />} />
            <Route path="*" element={<ErrorPage />} />
          </Routes>
        </Suspense>
      </Router>
    </ConfigProvider>
  );
};

export default App;
