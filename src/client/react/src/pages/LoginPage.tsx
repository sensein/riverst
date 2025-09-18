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
  const { login, isAuthenticated, googleAuthEnabled } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Redirect to intended page or home if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      const from = (location.state as any)?.from?.pathname || '/';
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, navigate, location]);

  // Load Google Identity Services script only if Google auth is enabled
  useEffect(() => {
    if (!googleAuthEnabled) {
      setIsScriptLoaded(true); // Skip loading script
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

  // Initialize Google Sign-In when script is loaded and Google auth is enabled
  useEffect(() => {
    if (isScriptLoaded && googleAuthEnabled) {
      // Small delay to ensure DOM is ready
      setTimeout(() => {
        initializeGoogleSignIn();
      }, 100);
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

  const handleBypassLogin = async () => {
    setIsGoogleLoading(true);
    try {
      await login(); // No token needed for bypass
      message.success('Development mode login successful!');
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
                : "Development mode - Click below to continue"
              }
            </Paragraph>
          </div>

          {!isScriptLoaded ? (
            <Spin
              indicator={<LoadingOutlined style={{ fontSize: 24 }} spin />}
              tip={googleAuthEnabled ? "Loading Google Sign-In..." : "Initializing..."}
            />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              {googleAuthEnabled ? (
                <div id="google-signin-button" />
              ) : (
                <Button
                  type="primary"
                  size="large"
                  onClick={handleBypassLogin}
                  loading={isGoogleLoading}
                  style={{ minWidth: '200px' }}
                >
                  Continue to App
                </Button>
              )}

              {isGoogleLoading && googleAuthEnabled && (
                <div style={{ marginTop: '16px' }}>
                  <Spin
                    indicator={<LoadingOutlined style={{ fontSize: 24 }} spin  />}
                    tip="Signing in..." />
                </div>
              )}
            </div>
          )}

          <div>
            <Paragraph type="secondary" style={{ fontSize: '13px', margin: 0, lineHeight: '1.6' }}>
              {googleAuthEnabled ? (
                <>
                  Access is restricted to authorized users only.
                  <br />
                  To request access, please contact{' '}
                  <a href="mailto:fabiocat@mit.edu">fabiocat@mit.edu</a>.
                </>
              ) : (
                "Development mode is active. Google authentication is disabled."
              )}
            </Paragraph>
          </div>
        </Space>
      </Card>
    </div>
  );
};

export default LoginPage;
