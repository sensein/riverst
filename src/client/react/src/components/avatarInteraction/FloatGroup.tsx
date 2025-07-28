// src/components/FloatGroup.tsx
import React from 'react';
import { FloatButton } from 'antd';
import { UpOutlined, LoadingOutlined } from '@ant-design/icons';
import DisconnectButton from './DisconnectButton'
import MuteButton from './MuteButton';
import CameraButton from './CameraButton';
import './FloatGroup.css'

import { usePipecatClientTransportState } from '@pipecat-ai/client-react'


interface FloatGroupProps {
  videoFlag: boolean
}

const FloatGroup: React.FC<FloatGroupProps> = ({ videoFlag }) => {
  const transportState = usePipecatClientTransportState()

  return (
    <FloatButton.Group
      trigger="click"
      type="default"
      className={transportState === 'ready' ? 'float-btn-group-connected' : 'float-btn-group-disconnected'}
      icon={
        transportState === 'ready'
          ? <UpOutlined />
          : <LoadingOutlined style={{ color: '#ff4d4f' }} />
      }
    >
      <DisconnectButton />
      { videoFlag && <CameraButton /> }
      <MuteButton />

    </FloatButton.Group>
  );
};

export default FloatGroup;
