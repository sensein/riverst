// src/pages/AvatarInteraction.tsx
import { useState, useEffect } from 'react'
import { useParams, useLocation, Navigate } from 'react-router-dom'
import { Spin, Alert } from 'antd'
import { RTVIProvider } from '../providers/RTVIProvider'
import AvatarInteractionContent from '../components/avatarInteraction/AvatarInteractionContent'

interface SettingsState {
  camera_settings: 'full_body' | 'half_body' | 'headshot'
  video_flag: boolean
  user_transcript: boolean
  bot_transcript: boolean
}

export default function AvatarInteraction() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const settings = useLocation().state as SettingsState | null

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // simple validation: sessionId and settings must both be present
    if (!sessionId) {
      setError('No session ID provided. Please start from the settings page.')
      setLoading(false)
      return
    }
    if (!settings) {
      setError('Missing interaction settings. Please make sure you have the correct link or return to the setup page.')
      // TODO: error page
      setLoading(false)
      return
    }
    // everything looks good
    setLoading(false)
  }, [sessionId, settings])

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }}>
        <Spin size="large" />
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ maxWidth: 600, margin: '40px auto' }}>
        <Alert type="error" message={error} showIcon />
      </div>
    )
  }

  // at this point sessionId & settings are valid
  return (
    <RTVIProvider sessionId={sessionId!} enableCam={settings!.video_flag}>
      <AvatarInteractionContent
        cameraType={settings!.camera_settings}
        videoFlag={settings!.video_flag}
        subtitlesEnabled={{
          user: settings!.user_transcript,
          bot: settings!.bot_transcript,
        }}
      />
    </RTVIProvider>
  )
}