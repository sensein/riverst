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
    connectionUrl: `/api/offer?session_id=${encodeURIComponent(
      sessionId
    )}`,
    iceServers: [
      {
        urls: [
          'stun:stun.l.google.com:19302',
          'stun:stun.l.google.com:5349',
          'stun:stun1.l.google.com:3478',
          'stun:stun1.l.google.com:5349',
          'stun:stun2.l.google.com:19302',
          'stun:stun2.l.google.com:5349',
          'stun:stun3.l.google.com:3478',
          'stun:stun3.l.google.com:5349',
          'stun:stun4.l.google.com:19302',
          'stun:stun4.l.google.com:5349',
        ],
      },
    ],
    waitForICEGathering: true
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
          }
        }
      });

  return <PipecatClientProvider client={client}>{children}</PipecatClientProvider>
}
