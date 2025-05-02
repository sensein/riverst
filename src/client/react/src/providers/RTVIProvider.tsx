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
  callbacks: {
    onTransportStateChanged: (state) => {
      console.log(`Transport state: ${state}`);
    },
    onConnected: () => {
      console.log('Connected');
    },
    onBotReady: () => {
      console.log('Bot is ready');
    },
    onDisconnected: () => {
      console.log('Disconnected');
    },
    onUserStartedSpeaking: () => {
      console.log('User started speaking');
    },
    onUserStoppedSpeaking: () => {
      console.log('User stopped speaking');
    },
    onBotStartedSpeaking: () => {
      console.log('Bot started speaking');
    },
    onBotStoppedSpeaking: () => {
      console.log('Bot stopped speaking');
    },
    onUserTranscript: (transcript) => {
      if (transcript.final) {
        console.log(`User transcript: ${transcript.text}`);
      }
    },
    onBotTranscript: (transcript) => {
      console.log(`Bot transcript: ${transcript.text}`);
    },
    onTrackStarted: (track, participant) => {
      if (participant?.local) return;
      console.log('Received a remote track', track);
      // You can render the track here (e.g., put it in a video element)
    },
    onServerMessage: (msg) => {
      console.log(`Server message: ${JSON.stringify(msg)}`);
    }
  },
});

export function RTVIProvider({ children }: PropsWithChildren) {
  return <RTVIClientProvider client={client}>{children}</RTVIClientProvider>;
}
