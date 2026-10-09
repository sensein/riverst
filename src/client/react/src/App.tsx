/**
 * App.tsx
 * Main entry point for the React application.
 * Sets up global providers, routing, and code-splitting.
 */

import { ConfigProvider } from 'antd';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Homepage from './pages/Homepage';
import { appTheme } from './theme';
import FullPageLoader from './components/FullPageLoader';
import ProtectedRoute from './components/ProtectedRoute';
import TeacherRoute from './components/TeacherRoute';
import { AuthProvider } from './contexts/AuthContext';

import { Suspense, lazy } from 'react';

/**
 * Lazy-loaded pages for code-splitting and faster initial load.
 */
const AvatarCreatorPage = lazy(() => import('./pages/AvatarCreatorPage'));
const AvatarUploadPage = lazy(() => import('./pages/AvatarUploadPage'));
const AvatarInteraction = lazy(() => import('./pages/AvatarInteraction'));
const AvatarInteractionSettings = lazy(() => import('./pages/AvatarInteractionSettings'));
const SessionsList = lazy(() => import('./pages/SessionsList'));
const SessionDetail = lazy(() => import('./pages/SessionDetail'));
const LoginPage = lazy(() => import('./pages/LoginPage'));
const ErrorPage = lazy(() => import('./pages/ErrorPage'));
const AudioPlayerPage = lazy(() => import('./pages/AudioPlayerPage'));
const ListenToAudioBookPage = lazy(() => import('./pages/ListenToAudioBookPage'));
const KivaCodeEntry = lazy(() => import('./pages/KivaCodeEntry'));
const ClassOverview = lazy(() => import('./pages/teacher/ClassOverview'));
const TeacherStudentDetail = lazy(() => import('./pages/teacher/StudentDetail'));
const TeacherSessionDetail = lazy(() => import('./pages/teacher/SessionDetail'));
const WordInsights = lazy(() => import('./pages/teacher/WordInsights'));
const StudentReport = lazy(() => import('./pages/teacher/StudentReport'));

/**
 * AuthenticatedRoutes
 * Wraps all routes that require authentication and the AuthProvider.
 * ProtectedRoute ensures only authenticated users can access these pages.
 */
const AuthenticatedRoutes = () => (
  <AuthProvider>
    <Routes>
      {/* Login route (no protection) */}
      <Route path="/login" element={<LoginPage />} />

      {/* Protected routes */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Homepage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/avatar-upload"
        element={
          <ProtectedRoute>
            <AvatarUploadPage />
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
      <Route
        path="/listen-to-an-audio-book"
        element={
          <ProtectedRoute>
            <ListenToAudioBookPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/kiva"
        element={
          <ProtectedRoute>
            <KivaCodeEntry />
          </ProtectedRoute>
        }
      />

      {/* Teacher dashboard (teacher role only) */}
      <Route
        path="/teacher"
        element={
          <TeacherRoute>
            <ClassOverview />
          </TeacherRoute>
        }
      />
      <Route
        path="/teacher/words"
        element={
          <TeacherRoute>
            <WordInsights />
          </TeacherRoute>
        }
      />
      <Route
        path="/teacher/students/:id"
        element={
          <TeacherRoute>
            <TeacherStudentDetail />
          </TeacherRoute>
        }
      />
      <Route
        path="/teacher/students/:id/report"
        element={
          <TeacherRoute>
            <StudentReport />
          </TeacherRoute>
        }
      />
      <Route
        path="/teacher/sessions/:id"
        element={
          <TeacherRoute>
            <TeacherSessionDetail />
          </TeacherRoute>
        }
      />
      <Route path="*" element={<ErrorPage />} />
    </Routes>
  </AuthProvider>
);

/**
 * App
 * Sets up the global Ant Design theme, router, and suspense fallback.
 * - /avatar-interaction/:sessionId is accessible without authentication.
 * - /audio-player is accessible without authentication.
 * - All other routes are wrapped in AuthProvider and may require authentication.
 */
const App = () => {
  return (
    <ConfigProvider theme={appTheme}>
      <Router>
        <Suspense fallback={<FullPageLoader />}>
          <Routes>
            {/* Completely unauthenticated route - NO AuthProvider */}
            <Route path="/avatar-interaction/:sessionId" element={<AvatarInteraction />} />
            <Route
              path="/audio-player"
              element={
                <AudioPlayerPage />
              }
            />

            <Route path="/error" element={<ErrorPage />} />
            {/* All other routes - WITH AuthProvider (including login) */}
            <Route path="/*" element={<AuthenticatedRoutes />} />
          </Routes>
        </Suspense>
      </Router>
    </ConfigProvider>
  );
};

export default App;
