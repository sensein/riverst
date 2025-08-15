/**
 * main.tsx
 * React application entry point.
 * - Sets up Ant Design's App context for consistent theming and message handling.
 * - Uses React.StrictMode for highlighting potential problems.
 * - Renders the main App component into the root DOM node.
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './main.css';
import '@ant-design/v5-patch-for-react-19';
import { App as AntdApp } from 'antd';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <AntdApp>
    <React.StrictMode>
      <App />
    </React.StrictMode>
  </AntdApp>
);
