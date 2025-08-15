// src/providers/RTVIProvider.tsx
import { PropsWithChildren, useEffect } from 'react'
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
    connectionUrl: `/api/offer?session_id=${encodeURIComponent(
      sessionId
    )}`
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
          onDisconnected: () => {
            console.log('Client disconnected - checking if session ended naturally');

            // Check if this is a natural session end (from EndFrame) vs user leaving
            const endedSessions = JSON.parse(localStorage.getItem('endedSessions') || '[]');
            if (!endedSessions.includes(sessionId)) {
              // Mark as ended and navigate to end page
              endedSessions.push(sessionId);
              localStorage.setItem('endedSessions', JSON.stringify(endedSessions));
              console.log('Session ended naturally via EndFrame, navigating to end page');
              navigate(`/session-ended/${sessionId}`);
            }

          }
        }
      });

  // Handle user navigation away to prevent incorrect session end detection
  useEffect(() => {
    const handleBeforeUnload = () => {
      // When the user leaves, we mark the session as "ended" from the client-side
      // so that the onDisconnected handler doesn't mistake it for a server-initiated
      // session end and redirect to the session-ended page.
      const endedSessions = JSON.parse(localStorage.getItem('endedSessions') || '[]');
      if (!endedSessions.includes(sessionId)) {
        endedSessions.push(sessionId);
        localStorage.setItem('endedSessions', JSON.stringify(endedSessions));
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [sessionId]);

  return <PipecatClientProvider client={client}>{children}</PipecatClientProvider>
}
