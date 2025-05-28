// src/components/CameraButton.tsx
import { useState, useCallback } from 'react'
import { useRTVIClient, useRTVIClientEvent } from '@pipecat-ai/client-react'
import { FloatButton } from 'antd'
import { VideoCameraOutlined, VideoCameraAddOutlined } from '@ant-design/icons'
import { RTVIEvent, Participant } from '@pipecat-ai/client-js'

export default function CameraButton() {
  const client = useRTVIClient()
  const [isCameraOn, setIsCameraOn] = useState(true)

  const toggleCam = async () => {
    if (!client) return
    let isCamEnabled = client.isCamEnabled
    await client.enableCam(!isCamEnabled)
  }

  useRTVIClientEvent(
    RTVIEvent.TrackStopped,
    useCallback((track: MediaStreamTrack, participant?: Participant) => {
      if (participant?.local && track.kind === 'video') {
        setIsCameraOn(false)
      }
    }, [])
  )

  useRTVIClientEvent(
    RTVIEvent.TrackStarted,
    useCallback((track: MediaStreamTrack, participant?: Participant) => {
      if (participant?.local && track.kind === 'video') {
        setIsCameraOn(true)
      }
    }, [])
  )

  return (
    <FloatButton
      icon={
        isCameraOn
          ? <VideoCameraOutlined style={{ color: '#fff' }} />
          : <VideoCameraAddOutlined style={{ color: 'blue' }} />
      }
      type={isCameraOn ? 'primary' : 'default'}
      style={{
        right: 150,
        zIndex: 9999,
      }}
      onClick={toggleCam}
    />
  )
}
