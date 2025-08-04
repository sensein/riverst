/**
 * FullPageLoader.tsx
 * Displays a fullscreen loading spinner using Ant Design's Spin and LoadingOutlined.
 * Used as a fallback during lazy loading or long-running operations.
 */

import React from 'react';
import { Spin } from 'antd';
import { LoadingOutlined } from '@ant-design/icons';

/**
 * FullPageLoader
 * Renders a centered spinner overlaying the entire viewport.
 */
const FullPageLoader: React.FC = () => {
  return (
    <div style={loaderStyle}>
      <Spin indicator={<LoadingOutlined style={{ fontSize: 48 }} spin />} />
    </div>
  );
};

/**
 * loaderStyle
 * Styles for the fullscreen overlay and centering the spinner.
 */
const loaderStyle: React.CSSProperties = {
  position: 'fixed',
  top: 0,
  left: 0,
  width: '100vw',
  height: '100vh',
  backgroundColor: 'white',
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  zIndex: 1000,
};

export default FullPageLoader;
