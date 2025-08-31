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
  VoiceVisualizer
} from '@pipecat-ai/client-react'
import { RTVIEvent, Participant } from '@pipecat-ai/client-js'
import { Spin } from 'antd';
import { LoadingOutlined } from '@ant-design/icons';
import { usePipecatClientMicControl } from "@pipecat-ai/client-react";

// assuming you’ve moved these out into their own files:
import FloatGroup from './FloatGroup'
import SubtitleOverlay from './SubtitleOverlay'
import TalkingHeadWrapper from './TalkingHeadWrapper'

interface Props {
  embodiment: 'humanoid_avatar' | 'waveform'
  cameraType: 'full' | 'mid' | 'upper' | 'head'
  avatar: { id: number; modelUrl: string; gender: string }
  videoFlag: boolean
  subtitlesEnabled: { user: boolean; bot: boolean }
  onSessionEnd: (delay: number) => Promise<void>
}

export default function AvatarInteractionContent({
  embodiment,
  cameraType: initialCameraType,
  avatar,
  videoFlag,
  subtitlesEnabled: initialSubtitlesEnabled,
  onSessionEnd,
}: Props) {
  // ---- state derived from props ----
  const [cameraType] = useState(initialCameraType)
  const [subtitlesEnabled] = useState(initialSubtitlesEnabled)
  const [loading, setLoading] = useState(true)

  const { enableMic } = usePipecatClientMicControl();

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
    if (transportState === 'ready') {
      setLoading(false)
    }

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
    RTVIEvent.ServerMessage,
    useCallback(
      async (message: { type: string }) => {
        if (message.type === 'conversation-ended') {
          enableMic(false);
          await onSessionEnd(0);
        }
      },
      []
    )
  )

  useRTVIClientEvent(
    RTVIEvent.BotTranscript,
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

  useEffect(() => {
    if (embodiment == 'waveform') {
      setTimeout(() => {
        setInteractionPhase('ready');
      }, 1000);  // TODO: make this dynamic?
    }
  }, []);

  return (
    <div className="app">
      {loading && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            backgroundColor: 'white',
            zIndex: 10000,
          }}
        >
          <Spin indicator={<LoadingOutlined style={{ fontSize: 48 }} spin />} />
        </div>
      )}
      <FloatGroup
        onSessionEnd={onSessionEnd}
        videoFlag={videoFlag} />
      { embodiment == 'humanoid_avatar' && avatar && (
        <TalkingHeadWrapper
          avatar={avatar}
          cameraType={cameraType}
          onAvatarMounted={() => {
            if (interactionPhase === 'mounting') {
              setInteractionPhase('ready')
            }
          }}
        />
      )}
      {embodiment === 'waveform' && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            backgroundColor: '#e6f4ff',
            zIndex: 5,
          }}
        >
          <VoiceVisualizer
            participantType="bot"
            barColor="black"
            barLineCap="round"
            barCount={10}
            barGap={10}
            barWidth={30}
            barOrigin="center"
            barMaxHeight={1000}
          />
        </div>
      )}


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
