// src/components/AvatarInteractionContent.tsx
import React, {
    useState,
    useEffect,
    useCallback,
    useRef,
  } from 'react'
  import {
    useRTVIClientTransportState,
    useRTVIClientEvent,
    useRTVIClient,
    RTVIClientAudio,
  } from '@pipecat-ai/client-react'
  import { RTVIEvent, Participant } from '@pipecat-ai/client-js'
  
  // assuming you’ve moved these out into their own files:
  import DisconnectButton from './DisconnectButton'
  import BotVideo from './BotVideo'
  import SubtitleOverlay from './SubtitleOverlay'
  
  interface Props {
    cameraType: 'full_body' | 'half_body' | 'headshot'
    videoFlag: boolean
    subtitlesEnabled: { user: boolean; bot: boolean }
  }
  
  export default function AvatarInteractionContent({
    cameraType: initialCameraType,
    videoFlag,
    subtitlesEnabled: initialSubtitlesEnabled,
  }: Props) {
    const client = useRTVIClient()
    const transportState = useRTVIClientTransportState()
  
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
    const [interactionState, setInteractionState] = useState<
      'speaking' | 'listening' | null
    >(null)
  
    // ---- subtitles data ----
    const [subtitleList, setSubtitleList] = useState<
      { id: number; text: string; speaker: 'user' | 'bot' }[]
    >([])
    const subtitleIdRef = useRef(0)
    const SUBTITLE_DURATION_MS = 6000
  
    // ---- viseme buffering logic ----
    const visemeTimer = useRef<NodeJS.Timeout | null>(null)
    const startTimeRef = useRef<number | null>(null)
    const visemeBufferRef = useRef<{ duration: number; visemes: number[] }[]>(
      []
    )
    const usingRealVisemesRef = useRef(false)
    const timeoutHandlesRef = useRef<NodeJS.Timeout[]>([])
  
    const clearAllTimeouts = useCallback(() => {
      timeoutHandlesRef.current.forEach(clearTimeout)
      timeoutHandlesRef.current = []
    }, [])
  
    const scheduleVisemeBuffer = useCallback(() => {
      const buffer = visemeBufferRef.current
      const t0 = startTimeRef.current!
      const elapsed = performance.now() - t0
  
      let acc = 0,
        idx = 0
      while (
        idx < buffer.length &&
        acc + buffer[idx].duration * 1000 < elapsed
      ) {
        acc += buffer[idx].duration * 1000
        idx++
      }
      if (idx >= buffer.length) return
  
      const { duration, visemes } = buffer[idx]
      setCurrentViseme(visemes[0])
  
      const timeInto = elapsed - acc
      let offset = duration * 1000 - timeInto
      for (let j = idx + 1; j < buffer.length; j++) {
        const { duration: d, visemes: vs } = buffer[j]
        const h = setTimeout(() => setCurrentViseme(vs[0]), offset)
        timeoutHandlesRef.current.push(h)
        offset += d * 1000
      }
      // reset at end
      setCurrentViseme(0)
    }, [])
  
    const startRandomVisemeLoop = useCallback(() => {
      visemeTimer.current = setInterval(() => {
        setCurrentViseme(Math.floor(Math.random() * 22))
      }, 120)
    }, [])
  
    const stopRandomVisemeLoop = useCallback(() => {
      if (visemeTimer.current) {
        clearInterval(visemeTimer.current)
        visemeTimer.current = null
      }
    }, [])
  
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
  
    // auto‑connect when ready
    useEffect(() => {
        const connectIfReady = () => {
            if (
                interactionPhase === 'ready' &&
                    (transportState === 'disconnected')
                ) {
                  client.connect()
            }
        }
        connectIfReady()
    }, [interactionPhase, transportState, client])
    
  
    // event handlers
    useRTVIClientEvent(RTVIEvent.BotStartedSpeaking, () => {
      startTimeRef.current = performance.now()
      usingRealVisemesRef.current = false
      visemeBufferRef.current = []
      clearAllTimeouts()
      setInteractionState('speaking')
      if (!animationTrigger) setAnimationTrigger('idle')
      startRandomVisemeLoop()
    })
  
    useRTVIClientEvent(RTVIEvent.BotStoppedSpeaking, () => {
      startTimeRef.current = null
      usingRealVisemesRef.current = false
      visemeBufferRef.current = []
      clearAllTimeouts()
      stopRandomVisemeLoop()
      setCurrentViseme(0)
      setInteractionState(null)
    })
  
    useRTVIClientEvent(RTVIEvent.UserStartedSpeaking, () => {
      setInteractionState('listening')
      if (!animationTrigger) setAnimationTrigger('idle')
    })
  
    useRTVIClientEvent(RTVIEvent.UserStoppedSpeaking, () => {
      setInteractionState(null)
    })
  
    useRTVIClientEvent(
      RTVIEvent.ServerMessage,
      useCallback(
        (msg) => {
          if (msg.type === 'animation-event') {
            setAnimationTrigger(msg.payload.animation_id)
          }
          if (msg.type === 'visemes-event') {
            visemeBufferRef.current.push(
              ...(msg.payload as { duration: number; visemes: number[] }[])
            )
            if (startTimeRef.current != null) {
              if (!usingRealVisemesRef.current) {
                usingRealVisemesRef.current = true
                stopRandomVisemeLoop()
              }
              clearAllTimeouts()
              scheduleVisemeBuffer()
            }
          }
        },
        [clearAllTimeouts, scheduleVisemeBuffer, stopRandomVisemeLoop]
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
  
    useRTVIClientEvent(
      RTVIEvent.BotTranscript,
      useCallback(
        (data) => {
          if (subtitlesEnabled.bot) {
            addSubtitle(data.text, 'bot')
          }
        },
        [subtitlesEnabled.bot, addSubtitle]
      )
    )
  
    return (
      <div className="app">
        <DisconnectButton />
        <BotVideo
          cameraType={cameraType}
          setCameraType={setCameraType}
          animationTrigger={animationTrigger}
          setAnimationTrigger={setAnimationTrigger}
          currentViseme={currentViseme}
          interactionState={interactionState}
          onAvatarMounted={() => {
            if (interactionPhase === 'mounting') {
              setInteractionPhase('ready')
            }
          }}
          videoFlag={videoFlag}
        />
        <SubtitleOverlay subtitles={subtitleList} />
        <RTVIClientAudio />
      </div>
    )
}
  