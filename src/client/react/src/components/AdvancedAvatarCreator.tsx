/**
 * AdvancedAvatarCreator.tsx
 * Component for rendering the advanced avatar creator iframe.
 */

import React, { useEffect, useRef } from 'react';

interface AdvancedAvatarCreatorProps {
  onAvatarCreated: (avatarUrl: string, gender: string) => void;
  AdvancedAvatarCreatorUrl?: string;
}

const AdvancedAvatarCreator: React.FC<AdvancedAvatarCreatorProps> = ({
  onAvatarCreated,
  AdvancedAvatarCreatorUrl,
}) => {
  const iframeRef = useRef<HTMLIFrameElement>(null);

  //const defaultAdvancedAvatarCreatorUrl = 'https://create.readyplayer.me/avatar';
  const defaultAdvancedAvatarCreatorUrl = 'https://interactive-avatar-tijf7k.readyplayer.me/en/avatar';

  useEffect(() => {
    const handleMessage = async (event: MessageEvent) => {
      const origin = new URL(AdvancedAvatarCreatorUrl || defaultAdvancedAvatarCreatorUrl).origin;

      // Ensure the message comes from the correct origin
      if (event.origin !== origin) return;

      const json = parseJson(event.data);

      // Check if the message contains the avatar URL
      if (typeof event.data === 'string' && event.data.startsWith('https://models.readyplayer.me/')) {
        const avatarUrl = event.data;
        const modifiedUrl = `${avatarUrl}?morphTargets=ARKit,Oculus+Visemes,mouthOpen,mouthSmile,eyesClosed,eyesLookUp,eyesLookDown&textureSizeLimit=1024&textureFormat=png`;

        // Extract avatar ID from the URL
        const avatarIdMatch = avatarUrl.match(/\/([^/]+)\.glb$/);
        const avatarId = avatarIdMatch ? avatarIdMatch[1] : null;

        let gender = null;

        if (avatarId) {
          try {
            const response = await fetch(`https://models.readyplayer.me/${avatarId}.json`);
            if (response.ok) {
              const metadata = await response.json();
              gender = metadata.outfitGender || null;
            } else {
              console.error('Failed to fetch metadata:', response.statusText);
            }
          } catch (error) {
            console.error('Error fetching metadata:', error);
          }
        }

        onAvatarCreated(modifiedUrl, gender);
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

  const parseJson = (data: any): any | null => {
    try {
      return JSON.parse(JSON.stringify(data));
    } catch {
      return null;
    }
  };

  return (
    <iframe
      ref={iframeRef}
      src={`${AdvancedAvatarCreatorUrl || defaultAdvancedAvatarCreatorUrl}?frameApi&clearCache&quickStart=false&t=${Date.now()}`}
      allow="camera *;"
      style={{ width: '100%', height: '100%', border: 'none' }}
    />
  );
};

export default AdvancedAvatarCreator;
