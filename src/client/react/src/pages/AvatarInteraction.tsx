// App.tsx
import {
  RTVIClientAudio,
  useRTVIClientTransportState,
  useRTVIClientEvent,
} from '@pipecat-ai/client-react';
import { RTVIEvent } from '@pipecat-ai/client-js';
import { RTVIProvider } from '../providers/RTVIProvider';
import { ConnectButton } from '../components/ConnectButton';
import { StatusDisplay } from '../components/StatusDisplay';
import { DebugDisplay } from '../components/DebugDisplay';
import AvatarRenderer from '../components/AvatarRenderer';
import './AvatarInteraction.css';
import { useEffect, useState, useCallback, useRef } from 'react';
import axios from 'axios';

/*
interface VisemeEntry {
  viseme: number;
  duration: number;
}
*/

function BotVideo() {
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [animationTrigger, setAnimationTrigger] = useState<string | null>(null);
  const [cameraType, setCameraType] = useState<'full_body' | 'half_body' | 'headshot'>('headshot');
  const [currentViseme, setCurrentViseme] = useState<number | null>(null);

  const visemeTimer = useRef<NodeJS.Timeout | null>(null);

  const log = (msg: string) => console.log(`[${new Date().toISOString()}] ${msg}`);
  
  const startRandomVisemeLoop = useCallback(() => {
    log('Starting random viseme loop...');
    visemeTimer.current = setInterval(() => {
      const randomViseme = Math.floor(Math.random() * 22); // 0 to 21
      setCurrentViseme(randomViseme);
    }, 120); // 0.12 seconds
  }, []);

  const stopRandomVisemeLoop = useCallback(() => {
    log('Stopping viseme loop and resetting to 0...');
    if (visemeTimer.current) {
      clearInterval(visemeTimer.current);
      visemeTimer.current = null;
    }
    setCurrentViseme(0);
  }, []);

  useRTVIClientEvent(
    RTVIEvent.BotStartedSpeaking,
    useCallback(() => {
      log('[QQQ] Bot started speaking');
      startRandomVisemeLoop();
    }, [startRandomVisemeLoop])
  );

  useRTVIClientEvent(
    RTVIEvent.BotStoppedSpeaking,
    useCallback(() => {
      log('[QQQ] Bot stopped speaking');
      stopRandomVisemeLoop();
    }, [stopRandomVisemeLoop])
  );

  /*
  useRTVIClientEvent(
    RTVIEvent.ServerMessage,
    useCallback((data: any) => {
      if (data.type === 'visemes-event' && Array.isArray(data.payload)) {
        log(`[QQQ] Visemes received: ${JSON.stringify(data.payload)}`);
      }
    }, [])
  );
  */

  useEffect(() => {
    const fetchAvatar = async () => {
      try {
        const response = await axios.get('http://localhost:7860/avatar');
        const url = response.data.avatar_url;
        if (url) {
          setAvatarUrl(url);
        }
      } catch (error) {
        console.error('Failed to fetch avatar:', error);
      }
    };

    fetchAvatar();
  }, []);

  const triggerDance = () => setAnimationTrigger('dance');

  if (!avatarUrl) return <div>Loading avatar...</div>;

  return (
    <div className="bot-container">
      <div style={{ width: '800px', height: '600px', position: 'relative' }}>
        <div style={{ position: 'absolute', top: 20, left: '50%', transform: 'translateX(-50%)', zIndex: 10 }}>
          <button onClick={() => setCameraType('full_body')}>Full Body</button>
          <button onClick={() => setCameraType('half_body')}>Half Body</button>
          <button onClick={() => setCameraType('headshot')}>Headshot</button>
        </div>

        <AvatarRenderer
          avatarUrl={avatarUrl}
          bodyAnimation={animationTrigger}
          onAnimationEnd={() => setAnimationTrigger(null)}
          cameraType={cameraType}
          currentViseme={currentViseme}
        />

        <div style={{ position: 'absolute', bottom: 20, left: '50%', transform: 'translateX(-50%)' }}>
          <button onClick={triggerDance}>Dance</button>
        </div>
      </div>
    </div>
  );
}


function AppContent() {
  return (
    <div className="app">
      <div className="status-bar">
        <StatusDisplay />
        <ConnectButton />
      </div>

      <div className="main-content">
        <BotVideo />
      </div>

      <DebugDisplay />
      <RTVIClientAudio />
    </div>
  );
}

function App() {
  return (
    <RTVIProvider>
      <AppContent />
    </RTVIProvider>
  );
}

export default App;
