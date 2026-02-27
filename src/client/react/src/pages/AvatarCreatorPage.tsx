/**
 * AvatarCreatorPage.tsx
 * Allows users to choose an avatar for interaction.
 * - Fetches avatars from backend
 * - Displays each avatar with an interactive card
 * - Saves selected avatar to localStorage
 * - Uses Ant Design's Layout and Card components, styled via theme.tsx
 */

import { useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  Row,
  Col,
  Card,
  Typography,
  Divider,
  Popconfirm,
  message,
  Button,
  Layout,
  Tag,
} from 'antd';
import { ArrowLeftOutlined, CheckCircleFilled, DeleteOutlined, WarningOutlined } from '@ant-design/icons';
import AvatarRenderer from '../components/AvatarRenderer';

const { Title, Paragraph } = Typography;
const { Content } = Layout;

// Avatar shape/type
type Avatar = {
  id: string;
  name: string;
  modelUrl: string;
};

type UploadedAvatar = {
  modelUrl: string;
  gender: string;
  corrupted?: boolean;
};

const readSelectedModelUrl = (): string | null => {
  try {
    const raw = localStorage.getItem('selectedAvatar');
    return raw ? JSON.parse(raw).modelUrl ?? null : null;
  } catch {
    return null;
  }
};

const AvatarCreatorPage = () => {
  const [avatars, setAvatars] = useState<Avatar[]>([]);
  const [uploadedAvatars, setUploadedAvatars] = useState<UploadedAvatar[]>([]);
  const [selectedModelUrl, setSelectedModelUrl] = useState<string | null>(readSelectedModelUrl);
  const navigate = useNavigate();
  const { authRequest } = useAuth();

  // Fetch avatar data and uploaded avatars on mount
  useEffect(() => {
    const fetchAvatars = async () => {
      try {
        const response = await axios.get('/api/avatars');
        setAvatars(response.data);
      } catch (error) {
        console.error('Failed to fetch avatars:', error);
        message.error('Could not load avatars.');
      }
    };

    fetchAvatars();

    const fetchUploadedAvatars = async () => {
      try {
        const response = await authRequest.get('/api/my-avatars');
        const serverAvatars: UploadedAvatar[] = response.data;

        setUploadedAvatars(serverAvatars);
        localStorage.setItem('uploadedAvatars', JSON.stringify(serverAvatars));

        // If the selected avatar is an upload that no longer exists on the server,
        // clear it so the user isn't stuck with a broken selection.
        const selected = localStorage.getItem('selectedAvatar');
        if (selected) {
          try {
            const parsed = JSON.parse(selected);
            const isUpload = parsed.modelUrl?.startsWith('/uploads/');
            const serverEntry = serverAvatars.find((a) => a.modelUrl === parsed.modelUrl);
            const stillExists = !!serverEntry && !serverEntry.corrupted;
            if (isUpload && !stillExists) {
              localStorage.removeItem('selectedAvatar');
              setSelectedModelUrl(null);
            }
          } catch { /* ignore */ }
        }
      } catch (err) {
        console.error('Failed to fetch uploaded avatars:', err);
      }
    };

    fetchUploadedAvatars();
  }, []);

  const handleDeleteUpload = async (modelUrl: string) => {
    const filename = modelUrl.split('/').pop();
    if (!filename) return;

    try {
      await authRequest.delete(`/api/upload-avatar/${filename}`);
    } catch (err) {
      console.error('Failed to delete avatar file:', err);
      // Continue with localStorage cleanup even if server deletion fails
    }

    const updated = uploadedAvatars.filter((a) => a.modelUrl !== modelUrl);
    setUploadedAvatars(updated);
    localStorage.setItem('uploadedAvatars', JSON.stringify(updated));

    const selected = localStorage.getItem('selectedAvatar');
    if (selected) {
      try {
        if (JSON.parse(selected).modelUrl === modelUrl) {
          localStorage.removeItem('selectedAvatar');
          setSelectedModelUrl(null);
        }
      } catch { /* ignore */ }
    }

    message.success('Avatar deleted');
  };

  // Save avatar choice and navigate back
  const handleAvatarSelect = (avatar: Avatar | UploadedAvatar): void => {
    localStorage.setItem('selectedAvatar', JSON.stringify(avatar));
    setSelectedModelUrl(avatar.modelUrl);
    message.success(`Avatar selected`);
    navigate('/');
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Content style={{ padding: '2rem' }}>
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/')}
          type="default"
          style={{ marginBottom: '1rem' }}
        >
          Back
        </Button>

        <Title level={2}>Pick your avatar</Title>

        <Paragraph style={{ fontSize: 20 }}>
          Choose an avatar to interact with in the app. Click on an avatar to select it.
        </Paragraph>

        {uploadedAvatars.length > 0 && (
          <>
            <Title level={3}>My Uploads</Title>
            <Row gutter={[24, 24]}>
              {uploadedAvatars.map((avatar, idx) => {
                const deleteButton = (
                  <Popconfirm
                    title="Delete this avatar?"
                    description="This will permanently delete the file."
                    onConfirm={(e) => {
                      e?.stopPropagation();
                      handleDeleteUpload(avatar.modelUrl);
                    }}
                    onCancel={(e) => e?.stopPropagation()}
                    okText="Delete"
                    okButtonProps={{ danger: true }}
                    cancelText="Cancel"
                  >
                    <Button
                      type="text"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={(e) => e.stopPropagation()}
                    />
                  </Popconfirm>
                );

                if (avatar.corrupted) {
                  return (
                    <Col xs={24} sm={12} lg={6} key={avatar.modelUrl}>
                      <Card
                        title={
                          <span style={{ color: '#faad14' }}>
                            <WarningOutlined style={{ marginRight: 8 }} />
                            Corrupted Avatar {idx + 1}
                          </span>
                        }
                        style={{ height: '100%', cursor: 'default', opacity: 0.75 }}
                        extra={deleteButton}
                      >
                        <div style={{
                          height: '600px',
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '1rem',
                          color: '#8c8c8c',
                          textAlign: 'center',
                          padding: '1rem',
                        }}>
                          <WarningOutlined style={{ fontSize: 48, color: '#faad14' }} />
                          <span>
                            This avatar's files are incomplete or corrupted and cannot be used.
                            You can delete it to clean it up.
                          </span>
                        </div>
                      </Card>
                    </Col>
                  );
                }

                const isSelected = avatar.modelUrl === selectedModelUrl;
                return (
                  <Col xs={24} sm={12} lg={6} key={avatar.modelUrl}>
                    <Card
                      title={
                        <span>
                          {`Uploaded Avatar ${idx + 1}`}
                          {isSelected && (
                            <Tag color="success" icon={<CheckCircleFilled />} style={{ marginLeft: 8 }}>
                              Selected
                            </Tag>
                          )}
                        </span>
                      }
                      hoverable
                      onClick={() => handleAvatarSelect(avatar)}
                      style={{ height: '100%', cursor: 'pointer', ...(isSelected && { borderColor: '#52c41a', boxShadow: '0 0 0 2px rgba(82,196,26,0.2)' }) }}
                      extra={deleteButton}
                    >
                      <div style={{ height: '600px' }}>
                        <AvatarRenderer
                          avatarUrl={avatar.modelUrl}
                          cameraType="full"
                        />
                      </div>
                    </Card>
                  </Col>
                );
              })}
            </Row>
            <Divider />
          </>
        )}

        <Title level={3}>Pre-configured Avatars</Title>
        <Row gutter={[24, 24]}>
          {avatars.map((avatar) => {
            const isSelected = avatar.modelUrl === selectedModelUrl;
            return (
            <Col xs={24} sm={12} lg={6} key={avatar.id}>
              <Card
                title={
                  <span>
                    {avatar.name}
                    {isSelected && (
                      <Tag color="success" icon={<CheckCircleFilled />} style={{ marginLeft: 8 }}>
                        Selected
                      </Tag>
                    )}
                  </span>
                }
                hoverable
                onClick={() => handleAvatarSelect(avatar)}
                style={{ height: '100%', cursor: 'pointer', ...(isSelected && { borderColor: '#52c41a', boxShadow: '0 0 0 2px rgba(82,196,26,0.2)' }) }}
              >
                <div style={{ height: '600px' }}>
                  <AvatarRenderer
                    avatarUrl={avatar.modelUrl}
                    cameraType="full"
                  />
                </div>
              </Card>
            </Col>
            );
          })}
        </Row>
      </Content>
    </Layout>
  );
};

export default AvatarCreatorPage;
