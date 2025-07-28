// src/pages/AvatarInteraction.tsx
import { useState, useEffect } from 'react'
import { useParams, useLocation } from 'react-router-dom'
import { Spin, Alert } from 'antd'
import { RTVIProvider } from '../providers/RTVIProvider'
import AvatarInteractionContent from '../components/avatarInteraction/AvatarInteractionContent'
import axios from 'axios'

interface SettingsState {
  camera_settings: 'full' | 'mid' | 'upper' | 'head'
  video_flag: boolean
  user_transcript: boolean
  bot_transcript: boolean
}

export default function AvatarInteraction() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const location = useLocation()
  const initialSettings = location.state as SettingsState | null

  const [settings, setSettings] = useState<SettingsState | null>(initialSettings)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!sessionId) {
      setError('No session ID provided. Please start from the settings page.')
      setLoading(false)
      return
    }

    if (initialSettings) {
      setLoading(false)
      return
    }

    // Fetch settings from the API if not provided via state
    axios
      .get(`${import.meta.env.VITE_API_PROTOCOL}://${import.meta.env.VITE_API_HOST}:${import.meta.env.VITE_API_PORT}/api/session_config/${sessionId}`)
      .then((res) => setSettings(res.data))
      .catch(() => setError('Failed to load session configuration.'))
      .finally(() => setLoading(false))
  }, [sessionId, initialSettings])

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }}>
        <Spin size="large" />
      </div>
    )
  }

  if (error || !settings) {
    return (
      <div style={{ maxWidth: 600, margin: '40px auto' }}>
        <Alert
          type="error"
          message={error || 'Invalid session settings. Please return to the setup page.'}
          showIcon
        />
      </div>
    )
  }

  return (
    <RTVIProvider sessionId={sessionId!} enableCam={settings.video_flag}>
      <AvatarInteractionContent
        cameraType={settings.camera_settings}
        videoFlag={settings.video_flag}
        subtitlesEnabled={{
          user: settings.user_transcript,
          bot: settings.bot_transcript,
        }}
      />
    </RTVIProvider>
  )
}
