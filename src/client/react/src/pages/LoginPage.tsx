import React, { useState, useEffect } from 'react';
import { Card, Typography, message, Spin, Space, Button } from 'antd';
import { LoadingOutlined } from '@ant-design/icons';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate, useLocation } from 'react-router-dom';

const { Title, Paragraph } = Typography;

// Declare google object for TypeScript
declare global {
  interface Window {
    google: {
      accounts: {
        id: {
          initialize: (options: any) => void;
          renderButton: (element: HTMLElement, options: any) => void;
          prompt: () => void;
        };
      };
    };
  }
}

const LoginPage: React.FC = () => {
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);
  const [isScriptLoaded, setIsScriptLoaded] = useState(false);
  const { login, isAuthenticated, googleAuthEnabled, isLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Redirect to intended page or home if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      const from = (location.state as any)?.from?.pathname || '/';
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, navigate, location]);

  // Load Google Identity Services script
  useEffect(() => {
    if (!googleAuthEnabled) {
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.defer = true;
    script.onload = () => {
      setIsScriptLoaded(true);
    };
    document.head.appendChild(script);

    return () => {
      if (document.head.contains(script)) {
        document.head.removeChild(script);
      }
    };
  }, [googleAuthEnabled]);

  // Initialize Google Sign-In when script is loaded
  useEffect(() => {
    if (isScriptLoaded && googleAuthEnabled) {
      initializeGoogleSignIn();
    }
  }, [isScriptLoaded, googleAuthEnabled]);

  const initializeGoogleSignIn = () => {
    if (window.google) {
      window.google.accounts.id.initialize({
        client_id: import.meta.env.VITE_GOOGLE_CLIENT_ID,
        callback: handleGoogleResponse,
      });

      // Render the sign-in button
      const buttonElement = document.getElementById('google-signin-button');
      if (buttonElement) {
        window.google.accounts.id.renderButton(buttonElement, {
          theme: 'outline',
          size: 'large',
          width: 300,
        });
      }
    } else {
      console.error('Google object not available');
    }
  };

  const handleGoogleResponse = async (response: any) => {
    setIsGoogleLoading(true);
    try {
      await login(response.credential);
      message.success('Successfully logged in!');
    } catch (error: any) {
      message.error(error.message || 'Login failed. Please try again.');
    } finally {
      setIsGoogleLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)',
      padding: '20px'
    }}>
      <Card
        style={{
          width: '100%',
          maxWidth: 400,
          textAlign: 'center',
          boxShadow: '0 8px 32px rgba(0,0,0,0.1)',
          borderRadius: '16px'
        }}
      >
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div>
            <Title level={2} style={{ marginBottom: '8px' }}>
              Welcome to Riverst
            </Title>
            <Paragraph type="secondary">
              {googleAuthEnabled
                ? "Sign in with your Google account to access the reserved area"
                : "Authentication is currently being processed..."
              }
            </Paragraph>
          </div>

          {googleAuthEnabled && !isScriptLoaded ? (
            <Spin
              indicator={<LoadingOutlined style={{ fontSize: 24 }} spin />}
              tip="Loading Google Sign-In..."
            />
          ) : googleAuthEnabled ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <div id="google-signin-button" />

              {isGoogleLoading && (
                <div style={{ marginTop: '16px' }}>
                  <Spin
                    indicator={<LoadingOutlined style={{ fontSize: 24 }} spin  />}
                    tip="Signing in..." />
                </div>
              )}
            </div>
          ) : !isLoading && !isAuthenticated && !googleAuthEnabled ? (
            <div style={{ textAlign: 'center', color: '#ff4d4f' }}>
              <Title level={4} style={{ color: '#ff4d4f', marginBottom: '16px' }}>
                Authentication Error
              </Title>
              <Paragraph>
                Automatic login failed. Please refresh the page to try again.
              </Paragraph>
              <Button
                type="primary"
                onClick={() => window.location.reload()}
                style={{ marginTop: '8px' }}
              >
                Refresh Page
              </Button>
            </div>
          ) : (
            <div style={{ textAlign: 'center' }}>
              <Spin
                indicator={<LoadingOutlined style={{ fontSize: 24 }} spin />}
                tip="Authenticating..."
              />
            </div>
          )}

          <div>
            <Paragraph type="secondary" style={{ fontSize: '13px', margin: 0, lineHeight: '1.6' }}>
              Access is restricted to authorized users only.
              <br />
              To request access, please contact{' '}
              <a href="mailto:fabiocat@mit.edu">fabiocat@mit.edu</a>.
            </Paragraph>
          </div>
        </Space>
      </Card>
    </div>
  );
};

export default LoginPage;
