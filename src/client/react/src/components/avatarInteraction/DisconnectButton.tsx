// src/components/DisconnectButton.tsx
import { useState } from 'react'
import { usePipecatClient, usePipecatClientTransportState } from '@pipecat-ai/client-react'
import { useNavigate } from 'react-router-dom'
import { FloatButton, Popconfirm } from 'antd'
import { PoweroffOutlined, LoadingOutlined } from '@ant-design/icons'
import './DisconnectButton.css'
import { RTVIEvent } from '@pipecat-ai/client-js'

export default function DisconnectButton() {
  const client = usePipecatClient()
  const navigate = useNavigate()
  const [visible, setVisible] = useState(false)

  client?.on(RTVIEvent.Disconnected, () => {
    // console.log("[EVENT] User disconnected");
    navigate('/')
  });

  return (
    <>
      <FloatButton
        icon={<PoweroffOutlined style={{ color: '#fff' }} />}
        type="primary"
        className={'float-btn-connected'}
        style={{ right: 24, zIndex: 9999 }}
        onClick={() => setVisible(true)}
      />
      {visible && (
        <div style={{ position: 'absolute', right: 24, zIndex: 10000 }}>
          <Popconfirm
            title="Are you sure you want to disconnect?"
            open={visible}
            onOpenChange={(newOpen) => setVisible(newOpen)}
            onConfirm={async () => {
              await client?.disconnect()
            }}
            onCancel={() => setVisible(false)}
            okText="Yes"
            cancelText="No"
            placement="rightBottom"
            okButtonProps={{ danger: true }}
          />
        </div>
      )}
    </>
  )
}
