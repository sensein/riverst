// src/components/BotVideo.tsx
import { useEffect, useState, useRef, useCallback } from 'react'
import { useRTVIClientEvent } from '@pipecat-ai/client-react'
import { RTVIEvent, Participant } from '@pipecat-ai/client-js'
import AvatarRenderer from './AvatarRenderer'

interface BotVideoProps {
  cameraType: 'full_body' | 'half_body' | 'headshot'
  setCameraType: (t: any) => void
  animationTrigger: string | null
  setAnimationTrigger: (t: any) => void
  currentViseme: number
  interactionState: 'speaking' | 'listening' | null
  onAvatarMounted?: () => void
  videoFlag: boolean
}

export default function BotVideo({
  cameraType,
  setCameraType,
  animationTrigger,
  setAnimationTrigger,
  currentViseme,
  interactionState,
  onAvatarMounted,
  videoFlag,
}: BotVideoProps) {
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null)
  const [showVideo, setShowVideo] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    fetch('http://localhost:7860/avatar')
      .then(res => res.json())
      .then(data => {
        setAvatarUrl(data.avatar_url)
        onAvatarMounted?.()
      })
      .catch(err => console.error('Failed to fetch avatar:', err))
  }, [])

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

  if (!avatarUrl) return null

  return (
    <div style={{ position: 'relative', width: '100vw', height: '100vh' }}>
      <AvatarRenderer
        avatarUrl={avatarUrl}
        bodyAnimation={animationTrigger}
        onAnimationEnd={() => {
          setAnimationTrigger(null)
        }}
        cameraType={cameraType}
        currentViseme={currentViseme}
        interactionState={interactionState}
      />
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
            opacity: showVideo ? 1 : 0,
            transition: 'opacity 0.3s ease-in-out',
          }}
        />
      )}
    </div>
  )
}
