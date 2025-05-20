// AdvancedAvatarCreator.tsx

import React, { useEffect, useRef } from 'react';

interface AdvancedAvatarCreatorProps {
  onAvatarCreated: (avatarUrl: string) => void;
  AdvancedAvatarCreatorUrl?: string;
}

const AdvancedAvatarCreator: React.FC<AdvancedAvatarCreatorProps> = ({ onAvatarCreated, AdvancedAvatarCreatorUrl }) => {
  const iframeRef = useRef<HTMLIFrameElement>(null);

  const defaultAdvancedAvatarCreatorUrl = 'https://interactive-avatar-tijf7k.readyplayer.me';
  //const defaultAdvancedAvatarCreatorUrl = 'https://create.readyplayer.me/avatar';

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      const origin = new URL(AdvancedAvatarCreatorUrl || defaultAdvancedAvatarCreatorUrl).origin;

      // Ensure the message comes from the correct origin
      if (event.origin !== origin) return;

      const json = parseJson(event.data);

      // Check if the message contains the avatar URL
      if (typeof event.data === 'string' && event.data.startsWith('https://models.readyplayer.me/')) {
        // Modify the URL to include morph targets
        const modifiedUrl = `${event.data}?morphTargets=mouthOpen,Oculus Visemes`;
        onAvatarCreated(modifiedUrl);
      } else if (json?.eventName === 'v1.frame.ready') {
        // Subscribe to events
        iframeRef.current?.contentWindow?.postMessage(
          JSON.stringify({
            target: 'readyplayerme',
            type: 'subscribe',
            eventName: 'v1.**',
          }),
          '*'
        );
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [onAvatarCreated, AdvancedAvatarCreatorUrl]);

  const parseJson = (data: any): any => {
    try {
      return JSON.parse(data);
    } catch {
      return null;
    }
  };

  return (
    <iframe
      ref={iframeRef}
      src={`${AdvancedAvatarCreatorUrl || defaultAdvancedAvatarCreatorUrl}?lang=en&frameApi&clearCache&quickStart=false&t=${Date.now()}`}
      allow="camera *;"
      style={{ width: '100%', height: '100%', border: 'none' }}
    />
  );
};

export default AdvancedAvatarCreator;