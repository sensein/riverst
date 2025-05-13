// src/components/DisconnectButton.tsx
import { useState } from 'react'
import { useRTVIClient, useRTVIClientTransportState } from '@pipecat-ai/client-react'
import { useNavigate } from 'react-router-dom'
import { FloatButton, Popconfirm } from 'antd'
import { PoweroffOutlined, LoadingOutlined } from '@ant-design/icons'
import './DisconnectButton.css'

export default function DisconnectButton() {
  const client = useRTVIClient()
  const transportState = useRTVIClientTransportState()
  const navigate = useNavigate()
  const [visible, setVisible] = useState(false)
  const isConnected = transportState === 'connected'

  return (
    <>
      <FloatButton
        icon={
          isConnected
            ? <PoweroffOutlined style={{ color: '#fff' }} />
            : <LoadingOutlined style={{ color: '#ff4d4f' }} />
        }
        type="primary"
        className={isConnected ? 'float-btn-connected' : 'float-btn-disconnected'}
        style={{ top: 24, right: 24, zIndex: 9999, cursor: isConnected ? 'pointer' : 'default' }}
        onClick={() => isConnected && setVisible(true)}
      />
      {visible && (
        <div style={{ position: 'absolute', top: 80, right: 24, zIndex: 10000 }}>
          <Popconfirm
            title="Are you sure you want to disconnect?"
            open={visible}
            onConfirm={async () => {
              await client.disconnect()
              navigate('/')
            }}
            onCancel={() => setVisible(false)}
            okText="Yes"
            cancelText="No"
            placement="topRight"
            okButtonProps={{ danger: true }}
          />
        </div>
      )}
    </>
  )
}
