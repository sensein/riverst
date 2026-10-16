// src/components/avatarInteraction/Whiteboard.tsx
// Classroom whiteboard: all transcript text (learner + Kiva) is "written" here,
// accumulating and auto-scrolling, replacing the old bottom subtitle bubbles.
import { useEffect, useRef } from 'react'

interface WhiteboardProps {
  subtitles: { id: number; text: string; speaker: 'user' | 'bot' }[]
}

// Marker colours, as on a real whiteboard.
const MARKER: Record<'user' | 'bot', string> = {
  bot: '#1565c0', // Kiva — blue marker
  user: '#2e7d32', // learner — green marker
}

export default function Whiteboard({ subtitles }: WhiteboardProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  // Keep the newest line in view as text is written.
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [subtitles])

  return (
    <div
      style={{
        position: 'absolute',
        top: '9vh',
        right: '3vw',
        width: 'min(660px, 46vw)',
        zIndex: 8,
        pointerEvents: 'none',
      }}
    >
      {/* aluminium frame */}
      <div
        style={{
          background: 'linear-gradient(#e9edf2, #cfd6df)',
          borderRadius: 14,
          padding: 12,
          boxShadow: '0 10px 24px rgba(0,0,0,0.22)',
        }}
      >
        {/* board surface */}
        <div
          ref={scrollRef}
          style={{
            background: '#ffffff',
            borderRadius: 6,
            height: '44vh',
            overflowY: 'auto',
            padding: '18px 24px',
            boxShadow: 'inset 0 0 14px rgba(0,0,0,0.06)',
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
            pointerEvents: 'auto',
          }}
        >
          {subtitles.length === 0 ? (
            <div
              style={{
                color: '#9aa6b2',
                fontStyle: 'italic',
                fontFamily: 'Roboto, sans-serif',
                fontSize: 18,
              }}
            >
              …
            </div>
          ) : (
            subtitles.map(({ id, text, speaker }) => (
              <div
                key={id}
                style={{
                  color: MARKER[speaker],
                  fontFamily: "'Kalam', 'Comic Sans MS', Roboto, sans-serif",
                  fontSize: 21,
                  lineHeight: 1.35,
                  fontWeight: 600,
                }}
              >
                <span
                  style={{
                    fontSize: 13,
                    fontWeight: 700,
                    opacity: 0.7,
                    marginRight: 8,
                    textTransform: 'uppercase',
                    letterSpacing: 0.5,
                  }}
                >
                  {speaker === 'bot' ? 'Kiva' : 'You'}
                </span>
                {text}
              </div>
            ))
          )}
        </div>
        {/* marker tray */}
        <div
          style={{
            margin: '10px auto 2px',
            width: '55%',
            height: 8,
            borderRadius: 4,
            background: '#b9c0ca',
          }}
        />
      </div>
    </div>
  )
}
