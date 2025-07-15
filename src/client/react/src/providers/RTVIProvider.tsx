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
    connectionUrl: `http://localhost:7860/api/offer?session_id=${encodeURIComponent(
            sessionId
          )}`
  });
  const navigate = useNavigate()

  // recreate client whenever sessionId changes
  const client = new PipecatClient({
        transport,
        enableMic: true,
        enableCam: enableCam,
        timeout: 10000,
        customConnectHandler: () => Promise.resolve(),
        callbacks: {
          onError: (error) => {
            console.error('RTVIClient error:', error);
            navigate('/error', {
              state: {
                message: "A RTVIClient error occurred. Please try again.",
                status: '500',
              }
            });
          }
        }
      });

  return <PipecatClientProvider client={client} enableCam={enableCam}>{children}</PipecatClientProvider>
}
