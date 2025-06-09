// src/components/MuteButton.tsx
import { FloatButton } from 'antd'
import { AudioOutlined, AudioMutedOutlined } from '@ant-design/icons'
import { useRTVIClientMicControl } from "@pipecat-ai/client-react";

export default function MuteButton() {
  const { enableMic, isMicEnabled } = useRTVIClientMicControl();

  const toggleMic = async () => {
    await enableMic(!isMicEnabled)
  }

  return (
    <FloatButton
      icon={
        !isMicEnabled
          ? <AudioMutedOutlined style={{ color: 'blue' }} />
          : <AudioOutlined style={{ color: '#fff' }} />
      }
      type={!isMicEnabled ? 'default' : 'primary'}
      style={{
        right: 90,
        zIndex: 9999,
      }}
      onClick={toggleMic}
    />
  )
}
