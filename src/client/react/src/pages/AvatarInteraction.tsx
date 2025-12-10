// src/pages/AvatarInteraction.tsx
import { useState, useEffect } from 'react'
import { useParams, useLocation } from 'react-router-dom'
import { Spin, Alert } from 'antd'
import { RTVIProvider } from '../providers/RTVIProvider'
import AvatarInteractionContent from '../components/avatarInteraction/AvatarInteractionContent'
import axios from 'axios'
import { getConsistentUserIdByDevice } from '../utils/userId';
import { LoadingOutlined } from '@ant-design/icons';

interface SettingsState {
  camera_settings: 'full' | 'mid' | 'upper' | 'head'
  avatar: {
    id: number
    modelUrl: string
    gender: string
  }
  embodiment: 'humanoid_avatar' | 'waveform'
  video_flag: boolean
  user_transcript: boolean
  bot_transcript: boolean
  prolific_campaign: boolean
}

export default function AvatarInteraction() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const location = useLocation()
  const initialSettings = location.state as SettingsState | null

  const [settings, setSettings] = useState<SettingsState | null>(initialSettings)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [prolificId, setProlificId] = useState<string | null>(null)


  // Check if this session has been marked as ended
  const isSessionEnded = async () => {
    try {
      const response = await axios.get(`/api/check_session_ended/${sessionId}`);
      return [response.data.ended, response.data.prolific_id];
    } catch (error) {
      console.error('Error checking session status:', error);
      return [false, null];
    }
  }

const onSessionEnd = async (delay: number) => {
  try {
    const response = await axios.get(`/api/end_session/${sessionId}`);
    const prolific_id = response.data.prolific_id;

    setTimeout(() =>
      setProlificId(prolific_id)
    , delay);
  } catch (error) {
    console.error("Failed to end session:", error);
    setError("Failed to end the session.");
  }
}

  useEffect(() => {
    (async () => {
      if (!sessionId) {
        setError('No session ID provided. Please start from the settings page.')
        setLoading(false)
        return
      }

      // Check if session has been ended
      const [isSessionEndedFlag, prolificId] = await isSessionEnded();
      if (isSessionEndedFlag) {
        setLoading(false)
        setProlificId(prolificId)
        return
      }

      const deviceFingerprint = await getConsistentUserIdByDevice();
      try {
        await axios.post('/api/session/add_device_fingerprint', {
          sessionid: sessionId,
          devicefingerprint: deviceFingerprint
        });

        const res = await axios.get(`/api/session_config/${sessionId}`);
        setSettings(res.data);
      } catch (err) {
        console.error("Error during session setup:", err);
        setError('Failed to register device fingerprint or load session configuration.');
      } finally {
        setLoading(false);
      }
    })();
  }, [sessionId])

  if (loading) {
    return (
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
    )
  }

  if (error || !settings) {
    return (
      <div
        style={{
          minHeight: '100vh',
          width: '100%',
          backgroundColor: '#e6f4ff',
          display: 'flex',
          padding: 24,
        }}
      >
        <div style={{ maxWidth: 600, width: '100%' }}>
          <Alert
            type="error"
            message={error || 'Invalid session settings. Please return to the setup page.'}
            showIcon
          />
        </div>
      </div>
    )
  } else if (prolificId) {
    return (
      <div
        style={{
          minHeight: '100vh',
          width: '100%',
          backgroundColor: '#e6f4ff',
          display: 'flex',
          padding: 24,
        }}
      >
        <div style={{ maxWidth: 600, margin: '40px auto' }}>
          <Alert
            type="success"
            showIcon
            message="Thank you! Your session has ended."
            description={
              settings.prolific_campaign ? (
                <div>
                  <p>Please copy the following ID and paste it into Prolific to complete your participation:</p>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    marginTop: '8px',
                    padding: '8px',
                    backgroundColor: '#f6f8fa',
                    border: '1px solid #d9d9d9',
                    borderRadius: '4px',
                    wordBreak: 'break-all'
                  }}>
                    <code style={{ flex: 1 }}>{prolificId}</code>
                    <button
                      onClick={() => navigator.clipboard.writeText(prolificId)}
                      style={{
                        background: '#1677ff',
                        color: 'white',
                        border: 'none',
                        padding: '4px 8px',
                        borderRadius: '4px',
                        cursor: 'pointer'
                      }}
                    >
                      Copy
                    </button>
                  </div>
                </div>
              ) : null
            }
          />
        </div>
      </div>
    )
  } else {
    return (
      <RTVIProvider sessionId={sessionId!} enableCam={settings.video_flag}>
        <AvatarInteractionContent
          embodiment={settings.embodiment}
          cameraType={settings.camera_settings}
          avatar={settings.avatar}
          videoFlag={settings.video_flag}
          subtitlesEnabled={{
            user: settings.user_transcript,
            bot: settings.bot_transcript,
          }}
          onSessionEnd={onSessionEnd}
        />
      </RTVIProvider>
    )
  }
}
