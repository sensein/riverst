// src/pages/AvatarInteractionSettings.tsx
import { useState, useEffect } from 'react'
import { useLocation, useNavigate, Link } from 'react-router-dom'
import { Spin, Alert } from 'antd'
import axios from 'axios'
import SettingsForm from '../components/SettingsForm'

export default function AvatarInteractionSettings() {
  const location = useLocation()
  const settingsUrl = (location.state as any)?.settingsUrl as string | undefined
  const [schema, setSchema] = useState<any>(null)
  const navigate = useNavigate()

  // fetch the form schema from the passed-in URL
  useEffect(() => {
    if (!settingsUrl) return
    const url = settingsUrl.startsWith('http')
      ? settingsUrl
      : `http://localhost:7860/${settingsUrl}`

    axios
      .get(url)
      .then(res => setSchema(res.data))
      .catch(err => console.error('Failed to load schema:', err))
  }, [settingsUrl])


  const onSubmit = async (values: any) => {
    try {
      // 1. Get avatar object from localStorage or server
      let avatar: any = null;
      const stored = localStorage.getItem('selectedAvatar');

      if (stored) {
        try {
          const parsed = JSON.parse(stored);
          if (parsed && parsed.modelUrl) {
            avatar = parsed;
          }
        } catch (err) {
          console.error('Failed to parse avatar from localStorage:', err);
        }
      }

      if (!avatar) {
        try {
          const response = await axios.get('http://localhost:7860/avatars');
          const avatars = response.data;
          if (avatars.length > 0) {
            avatar = avatars[0];
            localStorage.setItem('selectedAvatar', JSON.stringify(avatar));
          } else {
            console.warn('No avatars returned from server.');
          }
        } catch (err) {
          console.error('Failed to fetch avatars:', err);
        }
      }

      // 2. Compose full payload
      const fullPayload = {
        ...values,
        avatar,
      };

      // 3. Create session
      const res = await axios.post('http://localhost:7860/api/session', fullPayload);
      const sessionId: string = res.data.session_id;

      // 4. Navigate with fullPayload
      navigate(`/avatar-interaction/${sessionId}`, { state: fullPayload });
    } catch (err) {
      console.error('Failed to create session:', err);
    }
  };

  if (!settingsUrl) {
    return (
      <div style={{ maxWidth: 600, margin: '40px auto', padding: 20 }}>
        <Alert
          type="error"
          message="No activitysettings provided."
          description={
            <>
              Please start from the <Link to="/">home page</Link>.
            </>
          }
          showIcon
        />
      </div>
    )
  }

  if (!schema) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }}>
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div>
      <SettingsForm schema={schema} onSubmit={onSubmit} />
    </div>
  )
}
