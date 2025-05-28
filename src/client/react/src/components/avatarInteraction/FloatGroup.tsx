// src/components/FloatGroup.tsx
import React from 'react';
import { FloatButton } from 'antd';
import { UpOutlined, LoadingOutlined } from '@ant-design/icons';
import DisconnectButton from './DisconnectButton'
import MuteButton from './MuteButton';
import CameraButton from './CameraButton';
import './FloatGroup.css'

import { useRTVIClientTransportState } from '@pipecat-ai/client-react'


interface FloatGroupProps {}

const FloatGroup: React.FC<FloatGroupProps> = () => {
  const transportState = useRTVIClientTransportState()
  const isConnected = transportState === 'connected'

  return (
    <FloatButton.Group
      trigger="click"
      type="default"
      className={isConnected ? 'float-btn-group-connected' : 'float-btn-group-disconnected'}
      disabled={!isConnected}
      icon={
        isConnected
          ? <UpOutlined />
          : <LoadingOutlined style={{ color: '#ff4d4f' }} />
      }
    >
      <DisconnectButton />
      <CameraButton />
      <MuteButton />

    </FloatButton.Group>
  );
};

export default FloatGroup;
