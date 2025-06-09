import { useEffect } from 'react'
import { FloatButton } from 'antd'
import { VideoCameraOutlined, VideoCameraAddOutlined } from '@ant-design/icons'
import { useRTVIClientCamControl } from "@pipecat-ai/client-react";

export default function CameraButton() {
  const { enableCam, isCamEnabled } = useRTVIClientCamControl();

  // Sync with actual status on mount
  useEffect(() => {
    enableCam(isCamEnabled)
  }, [])

  const toggleCam = async () => {
    await enableCam(!isCamEnabled)
  }

  return (
    <FloatButton
      icon={
        isCamEnabled
          ? <VideoCameraOutlined style={{ color: '#fff' }} />
          : <VideoCameraAddOutlined style={{ color: 'blue' }} />
      }
      type={isCamEnabled ? 'primary' : 'default'}
      style={{ right: 150, zIndex: 9999 }}
      onClick={toggleCam}
    />
  )
}
