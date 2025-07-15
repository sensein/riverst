// src/components/AvatarInteractionContent.tsx
import React, {
  useState,
  useEffect,
  useCallback,
  useRef,
} from 'react'
import {
  usePipecatClientTransportState,
  useRTVIClientEvent,
  usePipecatClient,
  PipecatClientAudio,
} from '@pipecat-ai/client-react'
import { RTVIEvent, Participant } from '@pipecat-ai/client-js'

// assuming you’ve moved these out into their own files:
import FloatGroup from './FloatGroup'
import SubtitleOverlay from './SubtitleOverlay'
import TalkingHeadWrapper from './TalkingHeadWrapper'
import axios from 'axios';

  interface Props {
    cameraType: 'full' | 'mid' | 'upper' | 'head'
    videoFlag: boolean
    subtitlesEnabled: { user: boolean; bot: boolean }
    sessionId?: string,
    ttsType: string
  }

  export default function AvatarInteractionContent({
    cameraType: initialCameraType,
    videoFlag,
    subtitlesEnabled: initialSubtitlesEnabled,
    sessionId,
    ttsType
  }: Props) {
    // ---- state derived from props ----
    const [cameraType, setCameraType] = useState(initialCameraType)
    const [subtitlesEnabled] = useState(initialSubtitlesEnabled)

    // ---- internal interaction state ----
    const [interactionPhase, setInteractionPhase] = useState<
      'mounting' | 'ready'
    >('mounting')
    const [animationTrigger, setAnimationTrigger] = useState<string | null>(
      null
    )
    const [currentViseme, setCurrentViseme] = useState(0)

    type VisemeFrame = { duration: number; visemes: number[] };

    // Add state to hold the full viseme sequence
    const [visemeSequence, setVisemeSequence] = useState<VisemeFrame[]>([]);
    const [utterance, setUtterance] = useState<string | null>(null)

    const videoRef = useRef<HTMLVideoElement>(null)
    const [showVideo, setShowVideo] = useState(false)

    // ---- subtitles data ----
    const [subtitleList, setSubtitleList] = useState<
      { id: number; text: string; speaker: 'user' | 'bot' }[]
    >([])
    const subtitleIdRef = useRef(0)
    const SUBTITLE_DURATION_MS = 6000

    // ---- viseme buffering logic ----
    const startTimeRef = useRef<number | null>(null)
    const visemeBufferRef = useRef<{ duration: number; visemes: number[] }[]>(
      []
    )
    const usingRealVisemesRef = useRef(false)

    const client = usePipecatClient()
    const transportState = usePipecatClientTransportState()

    const addSubtitle = useCallback(
      (text: string, speaker: 'user' | 'bot') => {
        setSubtitleList((prev) => {
          const last = prev[prev.length - 1];
          if (last && last.text === text && last.speaker === speaker) {
            return prev; // Skip adding duplicate
          }

          const id = subtitleIdRef.current++;
          const updated = [...prev, { id, text, speaker }];

          setTimeout(() => {
            setSubtitleList((curr) => curr.filter((s) => s.id !== id));
          }, SUBTITLE_DURATION_MS);

          return updated;
        });
      },
      []
    );

    const isConnectingRef = useRef(false)
    const retryCountRef = useRef(0)

    const [myAvatar, setMyAvatar] = useState<string | null>(null);
    const delay = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms));


    useEffect(() => {
      const fetchAvatars = async () => {
        try {
          const response = await axios.get('http://localhost:7860/avatars');
          const avatars = response.data;
          if (avatars.length > 0) {
            setMyAvatar(avatars[0]);
          }
        } catch (error) {
          console.error('Failed to fetch avatars:', error);
        }
      };

      const stored = localStorage.getItem('selectedAvatar');
      if (stored) {
        try {
          setMyAvatar(JSON.parse(stored));
        } catch (err) {
          console.error('Failed to parse avatar from localStorage:', err);
        }
      } else {
        fetchAvatars();
      }
    }, []);

    useEffect(() => {
      let stuckTimeout: NodeJS.Timeout | null = null

      const connectIfReady = async () => {
        if (interactionPhase === 'ready' && transportState === 'disconnected' && !isConnectingRef.current) {
          console.log("✅ connecting")
          isConnectingRef.current = true
          retryCountRef.current = 0
          try {
            await delay(2000);  // required to avoid race condition
            await client?.connect()
          } catch (err) {
            console.error("❌ Connection failed:", err)
          } finally {
            isConnectingRef.current = false
          }
        }
      }

      connectIfReady()

      // handle stuck in initializing
      if (
        interactionPhase === 'ready' &&
        transportState === 'initializing' &&
        retryCountRef.current < 3 &&
        !isConnectingRef.current
      ) {
        stuckTimeout = setTimeout(async () => {
          console.warn("🚨 Still initializing, disconnecting to trigger retry.")
          retryCountRef.current += 1
          await client?.disconnect()
        }, 1500)
      }

      return () => {
        if (stuckTimeout) clearTimeout(stuckTimeout)
      }
    }, [interactionPhase, transportState, client])


    // event handlers
    useRTVIClientEvent(RTVIEvent.BotTranscript, (data) => {
      console.log("Bot Transcript:", data);
      setUtterance(data.text)
    })

    useRTVIClientEvent(
      RTVIEvent.TrackStarted,
      useCallback((track: MediaStreamTrack, participant?: Participant) => {
        if (participant?.local) return
        if (track.kind === 'video' && videoRef.current) {
          videoRef.current.srcObject = new MediaStream([track])
          setShowVideo(true)
        }
      }, [])
    )

    useRTVIClientEvent(
      RTVIEvent.TrackStopped,
      useCallback((track: MediaStreamTrack, participant?: Participant) => {
        if (participant?.local) return
        if (track.kind === 'video' && videoRef.current) {
          setShowVideo(false)
        }
      }, [])
    )

    useRTVIClientEvent(
      RTVIEvent.ServerMessage,
      useCallback(
        (msg) => {
          console.log("Received server message:", msg);
          if (msg.type === 'animation-event') {
            console.log("animation-event:", msg.payload.animation_id);
            setAnimationTrigger(msg.payload.animation_id)
          }
          if (msg.type === 'visemes-event') {
            // console.log("Received visemes-event:", msg.payload);
            const newFrames = msg.payload as VisemeFrame[];
            visemeBufferRef.current.push(...newFrames);

            if (startTimeRef.current != null) {
              setVisemeSequence(visemeBufferRef.current);
            }
          }
          if (msg.type === 'tts-event') {
            console.log("Received utterance-event:", msg.payload);
          }
        },
        []
      )
    )

    useRTVIClientEvent(
      RTVIEvent.UserTranscript,
      useCallback(
        (data) => {
          if (data.final && subtitlesEnabled.user) {
            addSubtitle(data.text, 'user')
          }
        },
        [subtitlesEnabled.user, addSubtitle]
      )
    )

    if (!myAvatar) { return }

    return (
      <div className="app">
        <FloatGroup
          videoFlag={videoFlag} />

        <TalkingHeadWrapper
          avatar={myAvatar}
          height={100}
          width={100}
          cameraType={cameraType}
          onAvatarMounted={() => {
            if (interactionPhase === 'mounting') {
              setInteractionPhase('ready')
            }
          }}
          utterance={utterance}
          animation={animationTrigger}
          sessionId={sessionId}
          ttsType={ttsType}
          subtitleFlag={subtitlesEnabled.bot}
          addSubtitle={addSubtitle}
        />
        <SubtitleOverlay subtitles={subtitleList} />
        <PipecatClientAudio />
        {videoFlag && (
          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            style={{
              position: 'absolute',
              top: 20,
              left: 20,
              width: 320,
              height: 240,
              borderRadius: 16,
              backgroundColor: 'black',
              border: '1px solid black',
              zIndex: 6,
              boxShadow: '0 0 10px rgba(0,0,0,0.3)',
              opacity: showVideo && !!client?.isCamEnabled ? 1 : 0,
              transition: 'opacity 0.3s ease-in-out',
            }}
          />
        )}
      </div>
    )
}
