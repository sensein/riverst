import { type PropsWithChildren } from 'react';
import { RTVIClient } from '@pipecat-ai/client-js';
import { SmallWebRTCTransport } from "@pipecat-ai/small-webrtc-transport";
import { RTVIClientProvider } from '@pipecat-ai/client-react';

const transport = new SmallWebRTCTransport();

const client = new RTVIClient({
  transport,
  params: {
    baseUrl: "http://localhost:7860/api/offer"
  },
  enableMic: true,
  enableCam: true,
  customConnectHandler: () => Promise.resolve(),
});

export function RTVIProvider({ children }: PropsWithChildren) {
  return <RTVIClientProvider client={client}>{children}</RTVIClientProvider>;
}
