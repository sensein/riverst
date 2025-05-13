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
      : `${window.location.origin}${settingsUrl}`

    axios
      .get(url)
      .then(res => setSchema(res.data))
      .catch(err => console.error('Failed to load schema:', err))
  }, [settingsUrl])

  const onSubmit = async (values: any) => {
    try {
      // send the full settings payload to your server to get a session_id
      const res = await axios.post('http://localhost:7860/api/session', values)
      const sessionId: string = res.data.session_id

      // navigate to the interaction page, passing the same values along
      navigate(`/avatar-interaction/${sessionId}`, { state: values })
    } catch (err) {
      console.error('Failed to create session:', err)
    }
  }

  if (!settingsUrl) {
    return (
      <div style={{ maxWidth: 600, margin: '40px auto', padding: 20 }}>
        <Alert
          type="error"
          message="No activity settings provided."
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
    <div style={{ maxWidth: 600, margin: '0 auto', padding: 20 }}>
      <SettingsForm schema={schema} onSubmit={onSubmit} />
    </div>
  )
}
