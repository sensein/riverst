// src/components/SubtitleOverlay.tsx
interface SubtitleOverlayProps {
  subtitles: { id: number; text: string; speaker: 'user' | 'bot' }[]
}

export default function SubtitleOverlay({ subtitles }: SubtitleOverlayProps) {
  return (
    <div
      style={{
        position: 'absolute',
        bottom: 40,
        left: '50%',
        transform: 'translateX(-50%)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        zIndex: 10,
        gap: 10,
      }}
    >
      {subtitles.map(({ id, text, speaker }) => (
        <div
          key={id}
          style={{
            background: speaker === 'user' ? 'rgba(255,255,255,0.85)' : 'rgba(0,0,0,0.8)',
            color: speaker === 'user' ? '#000' : '#fff',
            padding: '16px 32px',
            borderRadius: 12,
            fontSize: 20,
            fontFamily: 'Roboto Medium, Roboto, sans-serif',
            fontWeight: 500,
            maxWidth: '90vw',
            textAlign: 'center',
            boxShadow: '0 2px 10px rgba(0,0,0,0.25)',
          }}
        >
          {text}
        </div>
      ))}
    </div>
  )
}
