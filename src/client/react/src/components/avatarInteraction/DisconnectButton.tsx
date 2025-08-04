// src/components/DisconnectButton.tsx
import { useState } from 'react'
import { usePipecatClient } from '@pipecat-ai/client-react'
import { FloatButton, Popconfirm } from 'antd'
import { PoweroffOutlined } from '@ant-design/icons'
import './DisconnectButton.css'

interface DisconnectButtonProps {
  onSessionEnd: (delay: number) => Promise<void>
}

export default function DisconnectButton({ onSessionEnd }: DisconnectButtonProps) {
  const client = usePipecatClient()
  const [visible, setVisible] = useState(false)

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
              await onSessionEnd(0)
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
