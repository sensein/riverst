// DebugDisplay.tsx
import { useRef, useCallback } from 'react';
import {
  Participant,
  RTVIEvent,
  TransportState,
  TranscriptData,
  BotLLMTextData,
} from '@pipecat-ai/client-js';
import { useRTVIClient, useRTVIClientEvent } from '@pipecat-ai/client-react';
import './DebugDisplay.css';

export function DebugDisplay() {
  const lastUserTranscriptRef = useRef<string | null>(null);
  const lastBotTranscriptRef = useRef<string | null>(null);
  const debugLogRef = useRef<HTMLDivElement>(null);
  // const client = useRTVIClient();

  const log = useCallback((message: string) => {
    if (!debugLogRef.current) return;

    const entry = document.createElement('div');
    entry.textContent = `${new Date().toISOString()} - ${message}`;

    // Add styling based on message type
    if (message.startsWith('User: ')) {
      entry.style.color = '#2196F3'; // blue for user
    } else if (message.startsWith('Bot: ')) {
      entry.style.color = '#4CAF50'; // green for bot
    }

    debugLogRef.current.appendChild(entry);
    debugLogRef.current.scrollTop = debugLogRef.current.scrollHeight;
  }, []);

  // Log transcripts
  useRTVIClientEvent(
    RTVIEvent.UserTranscript,
    useCallback(
      (data: TranscriptData) => {
        // Only log final transcripts
        if (data.final && data.text !== lastUserTranscriptRef.current) {
          lastUserTranscriptRef.current = data.text;
          log(`User: ${data.text}`);
        }  
      },
      [log]
    )
  );

  useRTVIClientEvent(
    RTVIEvent.BotTranscript,
    useCallback(
      (data: BotLLMTextData) => {
        if (data.text !== lastBotTranscriptRef.current) {
          lastBotTranscriptRef.current = data.text;
          log(`Bot: ${data.text}`);
        }
      },
      [log]
    )
  );

  return (
    <div className="debug-panel">
      <h3>Subtitles</h3>
      <div ref={debugLogRef} className="debug-log" />
    </div>
  );
}
