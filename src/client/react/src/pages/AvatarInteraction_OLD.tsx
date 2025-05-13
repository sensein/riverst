// AvatarInteraction.tsx
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
import AvatarRenderer from '../components/avatarInteraction/AvatarRenderer';
import './AvatarInteraction.css';
import { useEffect, useState, useCallback, useRef } from 'react';
import axios from 'axios';
import { useRTVIClient } from '@pipecat-ai/client-react';


function BotVideo() {
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [animationTrigger, setAnimationTrigger] = useState<string | null>(null);
  const [cameraType, setCameraType] = useState<'full_body' | 'half_body' | 'headshot'>('headshot');
  const [currentViseme, setCurrentViseme] = useState<number>(0);
  const transportState = useRTVIClientTransportState();
  const rtviClient = useRTVIClient();
  const videoRef = useRef<HTMLVideoElement>(null);
  const [interactionState, setInteractionState] = useState<'speaking' | 'listening' | null>(null);

  // ————— Fallback random viseme loop —————
  const visemeTimer = useRef<NodeJS.Timeout | null>(null);
  const startRandomVisemeLoop = useCallback(() => {
    // log('[qqq] Starting random viseme loop...');
    visemeTimer.current = setInterval(() => {
      setCurrentViseme(Math.floor(Math.random() * 22));
    }, 120);
  }, []);
  const stopRandomVisemeLoop = useCallback(() => {
    if (visemeTimer.current) {
      clearInterval(visemeTimer.current);
      visemeTimer.current = null;
    }
    // setCurrentViseme(0);
  }, []);

  // ————— Buffering & scheduling real visemes —————
  const startTimeRef = useRef<number | null>(null);
  const visemeBufferRef = useRef<{ duration: number; visemes: number[] }[]>([]);
  const usingRealVisemesRef = useRef(false);
  const timeoutHandlesRef = useRef<NodeJS.Timeout[]>([]);

  const clearAllTimeouts = useCallback(() => {
    timeoutHandlesRef.current.forEach(clearTimeout);
    timeoutHandlesRef.current = [];
  }, []);

  const scheduleVisemeBuffer = useCallback(() => {
    const buffer = visemeBufferRef.current;
    const t0 = startTimeRef.current!;
    const elapsed = performance.now() - t0;

    let acc = 0;
    let idx = 0;
    // find current index based on elapsed
    while (idx < buffer.length && acc + buffer[idx].duration * 1000 < elapsed) {
      acc += buffer[idx].duration * 1000;
      idx++;
    }
    if (idx >= buffer.length) return;

    // play the "current" viseme immediately
    const first = buffer[idx];
    setCurrentViseme(first.visemes[0]);

    // schedule the rest
    const timeIntoFirst = elapsed - acc;
    let offset = first.duration * 1000 - timeIntoFirst;
    for (let j = idx + 1; j < buffer.length; j++) {
      const { duration, visemes } = buffer[j];
      const handle = setTimeout(() => {
        setCurrentViseme(visemes[0]);
      }, offset);
      timeoutHandlesRef.current.push(handle);
      offset += duration * 1000;
    }
    setCurrentViseme(0);
  }, []);

  const log = useCallback((msg: string) => {
    // console.log(`[${new Date().toISOString()}] ${msg}`);
  }, []);

  // ————— Events —————

  useRTVIClientEvent(
    RTVIEvent.BotStartedSpeaking,
    useCallback(() => {
      // log('[QQQ] Bot started speaking');
      // mark start, reset
      startTimeRef.current = performance.now();
      usingRealVisemesRef.current = false;
      visemeBufferRef.current = [];
      clearAllTimeouts();
      setInteractionState('speaking');
      if (!animationTrigger) {
        console.log("[ZZZ] Setting animation trigger to idle!!!!!");
        setAnimationTrigger('idle');
      }
      startRandomVisemeLoop();
    }, [log, clearAllTimeouts, startRandomVisemeLoop])
  );

  useRTVIClientEvent(
    RTVIEvent.BotStoppedSpeaking,
    useCallback(() => {
      // log('[QQQ] Bot stopped speaking');
      startTimeRef.current = null;
      usingRealVisemesRef.current = false;
      visemeBufferRef.current = [];
      clearAllTimeouts();
      stopRandomVisemeLoop();
      setCurrentViseme(0);
      setInteractionState(null);
    }, [log, clearAllTimeouts, stopRandomVisemeLoop])
  );

  useRTVIClientEvent(
    RTVIEvent.UserStartedSpeaking,
    useCallback(() => {
      log('[QQQ] User started speaking');
      setInteractionState('listening');
      if (!animationTrigger) {
        console.log("[ZZZ] Setting animation trigger to idle!!!!!");
        setAnimationTrigger('idle');
      }
    }, [log])
  );

  useRTVIClientEvent(
    RTVIEvent.UserStoppedSpeaking,
    useCallback(() => {
      log('[QQQ] User stopped speaking');
      setInteractionState(null);
    }, [log])
  );

  useRTVIClientEvent(
    RTVIEvent.ServerMessage,
    useCallback(
      (data: any) => {
        if (data.type === 'animation-event') {
          // - BODY ANIMATION - 
          const { animation_id } = data.payload;
          // log(`[QQQ] Animation event: ${animation_id}`);
          if (animation_id === 'dance') setAnimationTrigger('dance');
          else if (animation_id === 'wave') setAnimationTrigger('wave');
          else if (animation_id === 'i_dont_know') setAnimationTrigger('i_dont_know');
        } else if (data.type === 'phonemes-event-new') {
          console.log(`[TTT1] - ${JSON.stringify(data.payload)}`);
          // log(`[TTT] NEW Phonemes event: ${JSON.stringify(data.payload)}`);
        }
        // — VISEMES —
        if (data.type === 'visemes-event') {
          const payload = data.payload as { duration: number; visemes: number[] }[];
          console.log(`[TTT2] Visemes event: ${JSON.stringify(payload)}`);
          //log(`[TTT2] Visemes event: ${JSON.stringify(payload)}`);
          // append to buffer
          visemeBufferRef.current.push(...payload);

          // once speech has started, always re‑schedule
          if (startTimeRef.current !== null) {
            if (!usingRealVisemesRef.current) {
              usingRealVisemesRef.current = true;
              // log('[QQQ] Using real visemes');
              stopRandomVisemeLoop();
            }
            clearAllTimeouts();
            scheduleVisemeBuffer();
          }
        }
      },
      [log, stopRandomVisemeLoop, clearAllTimeouts, scheduleVisemeBuffer]
    )
  );

  // ————— Fetch avatar —————
  useEffect(() => {
    axios
      .get('http://localhost:7860/avatar')
      .then((resp) => setAvatarUrl(resp.data.avatar_url))
      .catch((err) => console.error('Failed to fetch avatar:', err));
  }, []);

  useEffect(() => {
    if (transportState === 'disconnected') {
      // log('[QQQ] Disconnected - clearing visemes and animations');

      // Stop animations and viseme loop
      clearAllTimeouts();
      stopRandomVisemeLoop();

      // Reset viseme and animation state
      setCurrentViseme(0);
      setAnimationTrigger(null);
    }
  }, [transportState, log, clearAllTimeouts, stopRandomVisemeLoop]);


  // ————— Triggers for body animations —————
  // const triggerDance = () => setAnimationTrigger('dance');
  // const triggerIDontKnow = () => setAnimationTrigger('i_dont_know');
  // const triggerWave = () => setAnimationTrigger('wave');

  useRTVIClientEvent(
    RTVIEvent.TrackStarted,
    useCallback((track: MediaStreamTrack, participant?: Participant) => {
      if (participant?.local) return;
      if (track.kind === 'video' && videoRef.current) {
        videoRef.current.srcObject = new MediaStream([track]);
      }
    }, [])
  );
  
  if (!avatarUrl) return <div>Loading avatar...</div>;

  return (
    <div className="bot-container" style={{ display: 'flex', gap: '20px' }}>
      {/* Avatar */}
      <div style={{ width: 800, height: 600, position: 'relative' }}>
        <AvatarRenderer
          avatarUrl={avatarUrl}
          bodyAnimation={animationTrigger}
          onAnimationEnd={() => setAnimationTrigger(null)}
          cameraType={cameraType}
          currentViseme={currentViseme}
          interactionState={interactionState}
        />
        <div
          style={{
            position: 'absolute',
            bottom: 20,
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 10,
          }}
        >
          <button onClick={() => setCameraType('full_body')}>Full Body</button>
          <button onClick={() => setCameraType('half_body')}>Half Body</button>
          <button onClick={() => setCameraType('headshot')}>Headshot</button>
        </div>
        {/*
        <div style={{ position: 'absolute', bottom: 20, left: '50%', transform: 'translateX(-50%)' }}>
          <button onClick={triggerDance}>Dance</button> 
          <button onClick={triggerIDontKnow}>I don't know</button> 
          <button onClick={triggerWave}>Wave</button>
        </div>
        */}
      </div>
      {/* Video */}
      <div style={{ width: 800, height: 600 }}>
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          style={{ width: '100%', height: '100%', backgroundColor: 'black' }}
        />
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
