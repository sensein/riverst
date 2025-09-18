/**
 * TalkingHeadWrapper.tsx
 * Component for rendering a talking avatar.
 */

import {
  useEffect,
  useRef,
  forwardRef,
  useCallback,
  useImperativeHandle,
} from "react";
import {
  useRTVIClientEvent,
  usePipecatClientTransportState,
} from "@pipecat-ai/client-react";
import { RTVIEvent } from "@pipecat-ai/client-js";

interface Props {
  avatar: { id: number; modelUrl: string; gender: string };
  cameraType: "full" | "mid" | "upper" | "head";
  onAvatarMounted?: () => void;
}

interface TalkingHeadAPI {
  stop: () => void;
  setMood: (mood: string) => void;
  stopSpeaking: () => void;
  playGesture: (gesture: string, duration?: number) => void;
  playPose: (posePath: string, onprogress: ((event: ProgressEvent) => void) | null, dur?: number) => void;
  speakAudio: (args: {
    audio: AudioBuffer;
    words?: string[];
    wtimes?: number[];
    wdurations?: number[];
    visemes?: string[];
    vtimes?: number[];
    vdurations?: number[];
  }) => void;
  setView: (view: string) => void;
}

const TalkingHeadWrapper = forwardRef<object, Props>((props, ref) => {
  const { avatar, cameraType, onAvatarMounted } = props;

  const divRef = useRef<HTMLDivElement>(null);
  const headRef = useRef<TalkingHeadAPI | null>(null);
  const readyRef = useRef(false);
  const onAvatarMountedRef = useRef(onAvatarMounted);
  const transportState = usePipecatClientTransportState();

  const validAnimationExtensions = ['.fbx', '.glb', '.gltf'];

  useEffect(() => {
    onAvatarMountedRef.current = onAvatarMounted;
  }, [onAvatarMounted]);

  useImperativeHandle(ref, () => headRef.current!, []);

  // Load and mount the avatar model
  useEffect(() => {
    let isMounted = true;

    import("./talkinghead/talkinghead.mjs").then((mod) => {
      if (!isMounted || !divRef.current) return;

      const head = new mod.TalkingHead(divRef.current, {
        ttsEndpoint: "N/A",
        lipsyncModules: ["en"],
        cameraView: "full",
        lightAmbientIntensity: 0,
        lightDirectIntensity: 0,
        lightDirectColor: "#fff",
      });

      const body = avatar.gender === "feminine" ? "F" : "M";

      head.showAvatar(
        {
          url: avatar.modelUrl,
          body,
          avatarMood: "neutral",
          lipsyncLang: "en",
        },
        () => {
          headRef.current = head;
          readyRef.current = true;
          onAvatarMountedRef.current?.();
        }
      );
    });

    return () => {
      isMounted = false;
      headRef.current?.stop?.();
      headRef.current = null;
    };
  }, [avatar]);

  // Set the camera view once transport is ready
  useEffect(() => {
    if (transportState === "ready" && readyRef.current) {
      setTimeout(() => {
        headRef.current?.setView(cameraType);
      }, 5000);
    }
  }, [transportState, cameraType]);

  // Handle when the user starts speaking
  useRTVIClientEvent(RTVIEvent.UserStartedSpeaking, () => {
    const head = headRef.current;
    if (!head) return;
    head.setMood("neutral");
    head.stopSpeaking();
  });

  // Helper to play animations or mood changes
  const handleAnimationEvent = (animation: string, duration?: number) => {
    const head = headRef.current;
    if (!head) return;

    const gestureMap: Record<string, string | { gesture: string; duration?: number }> = {
      wave: { gesture: "handup", duration: 2 },
      dance: "/animations/dance/dance.fbx",
      i_have_a_question: "index",
      thank_you: "namaste",
      i_dont_know: "shrug",
      ok: "ok",
      thumbup: "thumbup",
      thumbdown: "thumbdown",
    };

    const moodList = ["happy", "angry", "sad", "fear", "disgust", "love", "sleep"];

    if (gestureMap[animation]) {
      const val = gestureMap[animation];
      if (typeof val === "string") {
        // Check if it's a file path
        if (validAnimationExtensions.includes(val.split('.').pop() || '')) {
          head.playPose(val, null, duration); // for fbx animations
        } else {
          head.playGesture(val, duration);
        }
      } else if (typeof val === "object") {
        head.playGesture(val.gesture, duration || val.duration);
      } 
    } else if (moodList.includes(animation)) {
      head.setMood(animation);
      setTimeout(() => head.setMood("neutral"), duration ? duration * 1000 : 4000);
    }
  };

  // Helper to play viseme or word timings
  const handleVisemeEvent = (payload: any) => {
    const head = headRef.current;
    if (!head) return;

    const { duration = 0 } = payload;
    if (duration <= 0) return;

    const dummyAudio = new AudioBuffer({
      length: duration * 16000,
      sampleRate: 16000,
    });

    head.speakAudio({
      audio: dummyAudio,
      ...(payload.words && {
        words: payload.words,
        wtimes: payload.wtimes,
        wdurations: payload.wdurations,
      }),
      ...(payload.visemes && {
        visemes: payload.visemes,
        vtimes: payload.vtimes,
        vdurations: payload.vdurations,
      }),
    });
  };

  // Listen to server messages for animations and visemes
  useRTVIClientEvent(
    RTVIEvent.ServerMessage,
    useCallback((msg: any) => {
      if (msg.type === "animation-event") {
        handleAnimationEvent(msg.payload.animation_id, msg.payload.duration);
      } else if (msg.type === "visemes-event") {
        if (msg.payload) handleVisemeEvent(msg.payload);
        else console.warn("Invalid viseme payload:", msg.payload);
      }
    }, [])
  );

  return (
    <div
      ref={divRef}
      style={{
        width: "100%",
        height: "100vh",
        background: "#BAE0FF1A",
        overflow: "hidden",
      }}
    />
  );
});

export default TalkingHeadWrapper;
