// src/providers/RTVIProvider.tsx
import { PropsWithChildren } from 'react'
import { RTVIClient } from '@pipecat-ai/client-js'
import { SmallWebRTCTransport } from '@pipecat-ai/small-webrtc-transport'
import { RTVIClientProvider } from '@pipecat-ai/client-react'

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
  const transport = new SmallWebRTCTransport();

  // recreate client whenever sessionId changes
  const client = new RTVIClient({
        transport,
        params: {
          // inject sessionId into the offer URL
          baseUrl: `http://localhost:7860/api/offer?session_id=${encodeURIComponent(
            sessionId
          )}`
        },
        enableMic: true,
        enableCam: enableCam,
        customConnectHandler: () => Promise.resolve()
      });

  return <RTVIClientProvider client={client} enableCam={enableCam}>{children}</RTVIClientProvider>
}
