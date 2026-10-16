// src/components/avatarInteraction/SessionUserChip.tsx
// Top-right chip for KIVA sessions: shows the signed-in user + app version + a logout button.
// The /avatar-interaction route is intentionally OUTSIDE AuthProvider (students join without login),
// so this reads the persisted token directly instead of useAuth(). Renders nothing for anonymous
// (student-code) sessions where no token is present.
import { useEffect, useState } from 'react'
import axios from 'axios'

interface SessionUserChipProps {
  sessionId: string
}

export default function SessionUserChip({ sessionId }: SessionUserChipProps) {
  const [name, setName] = useState<string | null>(null)
  const [version, setVersion] = useState<string | null>(null)
  const [removing, setRemoving] = useState(false)

  useEffect(() => {
    const token = localStorage.getItem('auth_token')
    if (!token) return
    const h = { headers: { Authorization: `Bearer ${token}` } }
    axios
      .get('/api/auth/me', h)
      .then((r) => setName(r.data?.name || r.data?.email || null))
      .catch(() => {})
    axios
      .get('/api/kiva/version', h)
      .then((r) => setVersion(r.data?.version || null))
      .catch(() => {})
  }, [])

  if (!name) return null

  const logout = () => {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('selected_avatar')
    localStorage.removeItem('uploaded_avatars')
    window.location.href = '/'
  }

  const removeSession = async () => {
    if (removing) return
    if (!window.confirm('Remove this session and its transcript & audio? This cannot be undone.')) return
    setRemoving(true)
    const token = localStorage.getItem('auth_token')
    try {
      await axios.delete(`/api/kiva/sessions/${sessionId}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      window.location.href = '/workspace'
    } catch {
      setRemoving(false)
      window.alert('Could not remove the session. Please try again.')
    }
  }

  // "v2.0.1" -> "V2.0.1"; leave commit-hash fallbacks (local dev) as-is.
  const versionLabel = version && /\d+\.\d+/.test(version) ? 'V' + version.replace(/^v/i, '') : version

  return (
    <div
      style={{
        position: 'absolute',
        top: 16,
        right: 20,
        zIndex: 9,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        background: 'rgba(255,255,255,0.92)',
        borderRadius: 999,
        padding: '6px 10px 6px 14px',
        boxShadow: '0 2px 10px rgba(0,0,0,0.15)',
        fontFamily: 'Roboto, sans-serif',
      }}
    >
      <span style={{ fontSize: 18 }}>👤</span>
      <span style={{ fontWeight: 600, color: '#1f2a44', fontSize: 14 }}>{name}</span>
      {versionLabel && (
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            color: '#2656d8',
            background: '#eaf0ff',
            borderRadius: 6,
            padding: '2px 7px',
          }}
        >
          {versionLabel}
        </span>
      )}
      <button
        onClick={removeSession}
        disabled={removing}
        style={{
          border: '1px solid #e2b4b4',
          background: '#fff',
          color: '#c0392b',
          borderRadius: 999,
          padding: '5px 12px',
          fontSize: 13,
          fontWeight: 600,
          cursor: removing ? 'default' : 'pointer',
          opacity: removing ? 0.6 : 1,
        }}
      >
        {removing ? 'Removing…' : 'Remove session'}
      </button>
      <button
        onClick={logout}
        style={{
          border: 'none',
          background: '#2656d8',
          color: '#fff',
          borderRadius: 999,
          padding: '5px 12px',
          fontSize: 13,
          fontWeight: 600,
          cursor: 'pointer',
        }}
      >
        Log out
      </button>
    </div>
  )
}
