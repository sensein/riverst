// src/components/AvatarInteractionContent.tsx
import {
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
  }

  export default function AvatarInteractionContent({
    cameraType: initialCameraType,
    videoFlag,
    subtitlesEnabled: initialSubtitlesEnabled,
  }: Props) {
    // ---- state derived from props ----
    const [cameraType] = useState(initialCameraType)
    const [subtitlesEnabled] = useState(initialSubtitlesEnabled)

    // ---- internal interaction state ----
    const client = usePipecatClient()
    const transportState = usePipecatClientTransportState()

    const [interactionPhase, setInteractionPhase] = useState<
      'mounting' | 'ready'
    >('mounting')

    // ---- subtitles data ----
    const [subtitleList, setSubtitleList] = useState<
      { id: number; text: string; speaker: 'user' | 'bot' }[]
    >([])
    const subtitleIdRef = useRef(0)
    const SUBTITLE_DURATION_MS = 6000

    const addSubtitle = useCallback(
      (text: string, speaker: 'user' | 'bot') => {
        const id = subtitleIdRef.current++
        setSubtitleList((prev) => [...prev, { id, text, speaker }])
        setTimeout(
          () =>
            setSubtitleList((prev) => prev.filter((s) => s.id !== id)),
          SUBTITLE_DURATION_MS
        )
      },
      []
    )

    const isConnectingRef = useRef(false)
    const retryCountRef = useRef(0)
    const hasConnectedOnceRef = useRef(false)

    useEffect(() => {
      let stuckTimeout: NodeJS.Timeout | null = null

      const connectIfReady = async () => {
        // Connect only ONCE when avatar is ready and never again automatically
        if (
          interactionPhase === 'ready' &&
          transportState === 'disconnected' &&
          !hasConnectedOnceRef.current &&
          !isConnectingRef.current
        ) {
          // console.log("First-time connect attempt")
          isConnectingRef.current = true
          retryCountRef.current = 0
          try {
            await client?.connect()
            hasConnectedOnceRef.current = true  // Mark as done
          } catch (err) {
            console.error("❌ Connection failed:", err)
          } finally {
            isConnectingRef.current = false
          }
        }
      }

      connectIfReady()

      // Optional: attempt recovery from stuck 'initializing'
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
          hasConnectedOnceRef.current = false // Allow retry
        }, 1500)
      }

      return () => {
        if (stuckTimeout) clearTimeout(stuckTimeout)
      }
    }, [interactionPhase, transportState, client])


    useRTVIClientEvent(
      RTVIEvent.UserTranscript,
      useCallback(
        (data: { text: string; final: boolean }) => {
          if (data.final && subtitlesEnabled.user) {
            addSubtitle(data.text, 'user')
          }
        },
        [subtitlesEnabled.user, addSubtitle]
      )
    )

    useRTVIClientEvent(
      RTVIEvent.BotTtsText,
      useCallback(
        (data: { text: string }) => {
          if (subtitlesEnabled.bot) {
            addSubtitle(data.text, 'bot')
          }
        },
        [subtitlesEnabled.bot, addSubtitle]
      )
    )

    const videoRef = useRef<HTMLVideoElement>(null)
    const [showVideo, setShowVideo] = useState(false)

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

    const [myAvatar, setMyAvatar] = useState<{ id: number; modelUrl: string; gender: string } | null>(null);

    useEffect(() => {
      const fetchAvatars = async () => {
        try {
          const response = await axios.get(`/api/avatars`);
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


    return (
      <div className="app">
        <FloatGroup
          videoFlag={videoFlag} />
        {myAvatar &&
          <TalkingHeadWrapper
            avatar={myAvatar}
            cameraType={cameraType}
            onAvatarMounted={() => {
              if (interactionPhase === 'mounting') {
                setInteractionPhase('ready')
              }
            }}
          />}

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
