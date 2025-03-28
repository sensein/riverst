// App.tsx
import {
  RTVIClientAudio,
  RTVIClientVideo,
  useRTVIClientTransportState,
} from '@pipecat-ai/client-react';
import { RTVIProvider } from './providers/RTVIProvider';
import { ConnectButton } from './components/ConnectButton';
import { StatusDisplay } from './components/StatusDisplay';
import { DebugDisplay } from './components/DebugDisplay';
import AvatarRenderer from './components/AvatarRenderer';
import './App.css';
import { useState } from 'react';

function BotVideo() {
  const transportState = useRTVIClientTransportState();
  const isConnected = transportState !== 'disconnected';

  const avatarUrl =
    'https://models.readyplayer.me/66ecc27e8812191462c3290f.glb?morphTargets=mouthOpen,Oculus Visemes';

  const [animationTrigger, setAnimationTrigger] = useState<string | null>(null);
  const [cameraType, setCameraType] = useState<'full_body' | 'half_body' | 'headshot'>('headshot');

  const triggerDance = () => {
    setAnimationTrigger('dance');
  };

  return (
    <div className="bot-container">
      <div className="video-container">
        {isConnected && <RTVIClientVideo participant="bot" fit="cover" />}
      </div>

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
