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
