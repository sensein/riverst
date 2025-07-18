import React, {
  useEffect,
  useRef,
  forwardRef,
  useCallback,
  useImperativeHandle,
} from "react";
import {
  useRTVIClientEvent,
} from '@pipecat-ai/client-react'
import { RTVIEvent } from '@pipecat-ai/client-js'

interface Props {
  avatar: { id: number; modelUrl: string; gender: string };
  cameraType: "full" | "mid" | "upper" | "head";
  audioTrack?: MediaStreamTrack;
  onAvatarMounted?: () => void;
}

const TalkingHeadWrapper = forwardRef<any, Props>((props, ref) => {
  const {
    avatar,
    cameraType,
    audioTrack,
    onAvatarMounted,
  } = props;

  const divRef = useRef<HTMLDivElement>(null);
  const headRef = useRef<any>(null);
  const readyRef = useRef(false);

  useImperativeHandle(ref, () => headRef.current, []);

  /* -------------------------------------------------- mount avatar */
  useEffect(() => {
    let isMounted = true;

    import("./talkinghead/talkinghead.mjs").then((mod) => {
      if (!isMounted || !divRef.current) return;

      const head = new mod.TalkingHead(divRef.current, {
        ttsEndpoint: "N/A",  // TTS endpoint is not used in this component
        lipsyncModules: ["en"],  // Lipsync module is required for viseme support
        cameraView: "full",
        lightAmbientIntensity: 0,
        lightDirectIntensity: 0,
        lightDirectColor: "#000",
      });

      const body = avatar.gender === "feminine" ? "F" : "M";

      head.showAvatar(
        {
          url: avatar.modelUrl,
          body,
          avatarMood: "neutral",
          lipsyncLang: "en",  // Lipsync module is required for viseme support
        },
        () => {}
      );

      setTimeout(() => head.setView(cameraType), 1500);

      headRef.current = head;
      readyRef.current = true;
      onAvatarMounted?.();
    });

    return () => {
      isMounted = false;
      if (headRef.current?.stop) headRef.current.stop();
      headRef.current = null;
    };
  }, [avatar, cameraType]);

  /* ------------------------------------------------ state effect */
  useRTVIClientEvent(RTVIEvent.UserStartedSpeaking, () => {
    const head = headRef.current;
    if (!head) return;
    head.setMood("neutral");
    head.stopSpeaking();
  })

  /* ---------------------------------------------- animation effect */
  useRTVIClientEvent(
    RTVIEvent.ServerMessage,
    useCallback(
      (msg) => {
        const head = headRef.current;
        if (!head) return;

        if (msg.type === 'animation-event') {
          const animation = msg.payload.animation_id;
          switch (animation) {
            case "wave":
              head.playGesture("handup", 2);
              break;
            case "dance":
              head.playPose("/animations/dance/dance.fbx");
              break;
            case 'i_have_a_question':
              head.playGesture('index');
              break;
            case 'thank_you':
              head.playGesture('namaste');
              break;
            case 'i_dont_know':
              head.playGesture('shrug');
              break;
            case 'ok':
            case 'thumbup':
            case 'thumbdown':
              head.playGesture(animation);
              break;
            case "happy":
            case "angry":
            case "sad":
            case "fear":
            case "disgust":
            case "love":
            case "sleep":
              head.setMood(animation);
              setTimeout(() => head.setMood("neutral"), 4000);
              break;
            default:
          }
        }
        if (msg.type === 'visemes-event') {
          // console.log("[XXX] Visemes Event:", msg.payload)
          if (msg.payload && msg.payload.words) {
            const { words, wtimes, wdurations, duration } = msg.payload;
            // console.log("Words", words);
            // console.log("Durations", wdurations);
            // console.log("Wtimes", wtimes);
            // console.log("Duration", duration);
            if (duration && duration > 0) {
              // TODO: i need to replace the dummy audio with the actual audio
              const dummyAudio = new AudioBuffer({
                length: duration * 16000,  // duration is in seconds
                sampleRate: 16000,
              });
              // console.log("Audio", dummyAudio);

              head.speakAudio(
                {
                  audio: dummyAudio,
                  words: words,
                  wtimes: wtimes,
                  wdurations: wdurations,
                }
              );
            }
          } else if (msg.payload && msg.payload.visemes) {
            const { visemes, vtimes, vdurations, duration } = msg.payload;
            // console.log("Visemes", visemes);
            // console.log("Durations", vdurations);
            // console.log("Vtimes", vtimes);
            // console.log("Duration", duration);
            if (duration && duration > 0) {
              // TODO: i need to replace the dummy audio with the actual audio
              const dummyAudio = new AudioBuffer({
                length: duration * 16000,  // duration is in seconds
                sampleRate: 16000,
              });
              // console.log("Audio", dummyAudio);

              head.speakAudio(
                {
                  audio: dummyAudio,
                  visemes: visemes,
                  vtimes: vtimes,
                  vdurations: vdurations,
                }
              );
            }
          }
          else {
            console.warn("Invalid message payload:", msg.payload);
          }
        }
      },
      []
    )
  )

  /* ------------------------------------------------------- render */
  return (
    <div
      ref={divRef}
      style={{
        width: `${100}%`,
        height: `${100}vh`,
        background: "#BAE0FF1A",
        overflow: "hidden",
      }}
    />
  );
});

export default TalkingHeadWrapper;
