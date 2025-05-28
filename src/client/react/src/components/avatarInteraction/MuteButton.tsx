// src/components/MuteButton.tsx
import { useState } from 'react'
import { useRTVIClient } from '@pipecat-ai/client-react'
import { FloatButton } from 'antd'
import { AudioOutlined, AudioMutedOutlined } from '@ant-design/icons'

export default function MuteButton() {
  const client = useRTVIClient()
  const [isMuted, setIsMuted] = useState(false)

  const toggleMic = async () => {
    if (!client) return
    const newState = !isMuted
    await client.enableMic(!newState) // false disables, true enables
    setIsMuted(newState)
  }

  return (
    <FloatButton
      icon={
        isMuted
          ? <AudioMutedOutlined style={{ color: 'blue' }} />
          : <AudioOutlined style={{ color: '#fff' }} />
      }
      type={isMuted ? 'default' : 'primary'}
      style={{
        right: 90,
        zIndex: 9999,
      }}
      onClick={toggleMic}
    />
  )
}
