// src/providers/RTVIProvider.tsx
import { PropsWithChildren } from "react";
import { PipecatClient } from "@pipecat-ai/client-js";
import { SmallWebRTCTransport } from "@pipecat-ai/small-webrtc-transport";
import { PipecatClientProvider } from "@pipecat-ai/client-react";
import { useNavigate } from "react-router-dom";

interface RTVIProviderProps {
  sessionId: string;
  enableCam: boolean;
}

export function RTVIProvider({
  sessionId,
  enableCam,
  children,
}: PropsWithChildren<RTVIProviderProps>) {
  // Access environment variable correctly for React
  const waitForICEGathering =
    import.meta.env.VITE_WAIT_FOR_ICE_GATHERING === "true";

  // Optional TURN relay — REQUIRED for restrictive / symmetric-NAT networks (STUN alone can't
  // relay media there, so the avatar connects but has no audio). Configured via env so each
  // environment uses its own coturn + credentials; VITE_TURN_URL may be a comma-separated list
  // (e.g. "turn:<host>:3478?transport=tcp"). Omit all three to fall back to STUN-only.
  const turnUrl = import.meta.env.VITE_TURN_URL as string | undefined;
  const turnUser = import.meta.env.VITE_TURN_USERNAME as string | undefined;
  const turnCred = import.meta.env.VITE_TURN_CREDENTIAL as string | undefined;
  const turnServers =
    turnUrl && turnUser && turnCred
      ? [{ urls: turnUrl.split(",").map((u) => u.trim()), username: turnUser, credential: turnCred }]
      : [];

  // keep the same transport instance
  const transport = new SmallWebRTCTransport({
    connectionUrl: `/api/offer?session_id=${encodeURIComponent(sessionId)}`,
    iceServers: [
      {
        urls: [
          "stun:stun.l.google.com:19302",
          "stun:stun1.l.google.com:3478",
          "stun:stun2.l.google.com:19302",
          "stun:stun3.l.google.com:3478",
          "stun:stun4.l.google.com:19302",
        ],
      },
      ...turnServers,
    ],
    waitForICEGathering,
  });

  const navigate = useNavigate();

  // recreate client whenever sessionId changes
  const client = new PipecatClient({
    transport,
    enableMic: true,
    enableCam: enableCam,
    callbacks: {
      onError: (error) => {
        console.error("PipecatClient error:", error);
        navigate("/error", {
          state: {
            message: "A PipecatClient error occurred. Please try again.",
            status: "500",
          },
        });
      },
    },
  });

  return (
    <PipecatClientProvider client={client}>{children}</PipecatClientProvider>
  );
}
