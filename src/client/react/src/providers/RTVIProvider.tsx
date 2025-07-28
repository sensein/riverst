// src/providers/RTVIProvider.tsx
import { PropsWithChildren } from 'react'
import { PipecatClient } from '@pipecat-ai/client-js'
import { SmallWebRTCTransport } from '@pipecat-ai/small-webrtc-transport'
import { PipecatClientProvider } from '@pipecat-ai/client-react'
import { useNavigate } from 'react-router-dom'

interface RTVIProviderProps {
  sessionId: string,
  enableCam: boolean,
}

export function RTVIProvider({
  sessionId,
  enableCam,
  children
}: PropsWithChildren<RTVIProviderProps>) {
  // keep the same transport instance
  const transport = new SmallWebRTCTransport({
    connectionUrl: `${import.meta.env.VITE_API_PROTOCOL}://${import.meta.env.VITE_API_HOST}:${import.meta.env.VITE_API_PORT}/api/offer?session_id=${encodeURIComponent(
      sessionId
    )}`,
    iceServers: [
      { urls: "stun:stun.l.google.com:19302" },
      {
        urls: "turn:play.kivaproject.org:3478",
        username: "testuser",
        credential: "testpass"
      }
    ],
    // iceServers: ["stun:stun.l.google.com:19302", "turn:3.21.191.176:3478"],
  });
  const navigate = useNavigate()

  // recreate client whenever sessionId changes
  const client = new PipecatClient({
        transport,
        enableMic: true,
        enableCam: enableCam,
        callbacks: {
          onError: (error) => {
            console.error('PipecatClient error:', error);
            navigate('/error', {
              state: {
                message: "A PipecatClient error occurred. Please try again.",
                status: '500',
              }
            });
          },
          onServerMessage: (message) => {
            // Handle conversation ended message from server
            if (message.type === 'conversation-ended') {
              console.log('Conversation ended by server:', message.message);

              // Mark session as ended in localStorage
              const endedSessions = JSON.parse(localStorage.getItem('endedSessions') || '[]');
              if (!endedSessions.includes(sessionId)) {
                endedSessions.push(sessionId);
                localStorage.setItem('endedSessions', JSON.stringify(endedSessions));
              }

              // Navigate to session end page
              navigate(`/session-ended/${sessionId}`);
            }
          }
        }
      });

  return <PipecatClientProvider client={client}>{children}</PipecatClientProvider>
}
