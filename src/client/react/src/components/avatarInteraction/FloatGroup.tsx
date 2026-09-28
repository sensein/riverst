// src/components/FloatGroup.tsx
import React, { useEffect, useState } from 'react';
import { FloatButton } from 'antd';
import { UpOutlined, LoadingOutlined } from '@ant-design/icons';
import DisconnectButton from './DisconnectButton'
import MuteButton from './MuteButton';
import CameraButton from './CameraButton';
import './FloatGroup.css'

import { usePipecatClientTransportState } from '@pipecat-ai/client-react'


interface FloatGroupProps {
  onSessionEnd: (delay: number) => Promise<void>
  videoFlag: boolean
}

const FloatGroup: React.FC<FloatGroupProps> = ({ onSessionEnd, videoFlag }) => {
  const transportState = usePipecatClientTransportState()
  const connecting = transportState !== 'ready'

  // Count seconds until the transport is ready (i.e. until the bot can talk),
  // shown next to the still-spinning float button.
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    if (!connecting) return
    const startedAt = Date.now()
    const t = setInterval(() => setElapsed((Date.now() - startedAt) / 1000), 100)
    return () => clearInterval(t)
  }, [connecting])

  return (
    <>
      {connecting && (
        <div
          style={{
            position: 'fixed',
            right: 24,
            bottom: 80,
            zIndex: 1000,
            fontVariantNumeric: 'tabular-nums',
            color: '#ff4d4f',
            fontSize: 14,
          }}
        >
          {elapsed.toFixed(1)}s
        </div>
      )}
      <FloatButton.Group
        trigger="click"
        type="default"
        // @ts-expect-error: disabled works but is not typed
        disabled={transportState !== 'ready'}
        className={transportState === 'ready' ? 'float-btn-group-connected' : 'float-btn-group-disconnected'}
        icon={
          transportState === 'ready'
            ? <UpOutlined />
            : <LoadingOutlined style={{ color: '#ff4d4f' }} />
        }
      >
        <DisconnectButton onSessionEnd={onSessionEnd}/>
        { videoFlag && <CameraButton /> }
        <MuteButton />

      </FloatButton.Group>
    </>
  );
};

export default FloatGroup;
