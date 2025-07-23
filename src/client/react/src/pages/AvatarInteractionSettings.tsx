// src/pages/AvatarInteractionSettings.tsx
import { useState, useEffect } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import { Spin, Alert, Modal, Button, QRCode, Typography, Divider, Tooltip } from 'antd';
import { CopyOutlined } from '@ant-design/icons';

import axios from 'axios';
import SettingsForm from '../components/SettingsForm';
const { Paragraph, Text } = Typography;

export default function AvatarInteractionSettings() {
  const location = useLocation();
  interface LocationState {
    settingsUrl?: string;
  }
  const settingsUrl = (location.state as LocationState)?.settingsUrl;

  const [schema, setSchema] = useState<object | null>(null);
  const navigate = useNavigate();

  const [modalVisible, setModalVisible] = useState(false);
  const [sessionLink, setSessionLink] = useState('');
  const [sessionPayload, setSessionPayload] = useState<object | null>(null);

  // fetch the form schema from the passed-in URL
  useEffect(() => {
    if (!settingsUrl) return;
    const url = settingsUrl.startsWith('http')
      ? settingsUrl
      : `http://localhost:7860/${settingsUrl}`;

    axios
      .get(url)
      .then(res => setSchema(res.data))
      .catch(err => console.error('Failed to load schema:', err));
  }, [settingsUrl]);

  const onSubmit = async (values: object) => {
    try {
      let avatar: object | null = null;
      const stored = localStorage.getItem('selectedAvatar');

      if (stored) {
        try {
          const parsed = JSON.parse(stored);
          if (parsed && parsed.modelUrl) {
            avatar = parsed;
          }
        } catch (err) {
          console.error('Failed to parse avatar from localStorage:', err);
        }
      }

      if (!avatar) {
        try {
          const response = await axios.get(`http://localhost:7860/avatars`);
          const avatars = response.data;
          if (avatars.length > 0) {
            avatar = avatars[0];
            localStorage.setItem('selectedAvatar', JSON.stringify(avatar));
          } else {
            console.warn('No avatars returned from server.');
          }
        } catch (err) {
          console.error('Failed to fetch avatars:', err);
        }
      }

      const fullPayload = {
        ...values,
        avatar,
      };

      console.log(fullPayload);

      const res = await axios.post(`http://localhost:7860/api/session`, fullPayload);
      const sessionId: string = res.data.session_id;
      const link = `/avatar-interaction/${sessionId}`;

      setSessionLink(link);
      setSessionPayload(fullPayload);
      setModalVisible(true);
    } catch (err) {
      console.error('Failed to create session:', err);
    }
  };

  if (!settingsUrl) {
    return (
      <div style={{ maxWidth: 600, margin: '40px auto', padding: 20 }}>
        <Alert
          type="error"
          message="No activity settings provided."
          description={
            <>
              Please start from the <Link to="/">home page</Link>.
            </>
          }
          showIcon
        />
      </div>
    );
  }

  if (!schema) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }}>
        <Spin size="large" />
      </div>
    );
  }

  const fullLink = window.location.origin + sessionLink;

  return (
    <div>
      <SettingsForm schema={schema} onSubmit={onSubmit} />

      <Modal
        title="Session created"
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={null}
      >
        <Paragraph>Scan the QR code or copy the link below to invite others to join the session.</Paragraph>

        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16 }}>
          <div style={{ textAlign: 'center', flex: 1 }}>
            <QRCode
              value={window.location.origin + sessionLink}
              size={160}
              icon='/logo/riverst_black.svg'
              iconSize={60}
            />
          </div>
          <div style={{ flex: 2, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <Text strong>Link:</Text>
                        <div style={{ display: 'flex', alignItems: 'center', marginTop: 8 }}>
                          <Text
              copyable={{
                text: fullLink,
                icon: [
                  <Tooltip title="Copy link" key="copy">
                    <CopyOutlined style={{ marginLeft: 8, color: '#1890ff' }} />
                  </Tooltip>,
                  <span style={{ marginLeft: 8 }}>Copied!</span>
                ],
              }}
              style={{ fontFamily: 'monospace', backgroundColor: '#f5f5f5', padding: '4px 8px', borderRadius: 4 }}
            >
              {fullLink}
            </Text>
            </div>
          </div>
        </div>

        <Divider orientation="center">
          OR
        </Divider>

        <Paragraph>Click on the button below to begin with the session.</Paragraph>
        <Button
          type="primary"
          block
          size="large"
          onClick={() => navigate(sessionLink, { state: sessionPayload })}
        >
          Start the session
        </Button>
      </Modal>

    </div>
  );
}
