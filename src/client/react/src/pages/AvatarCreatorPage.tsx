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
import {
  Row,
  Col,
  Card,
  Typography,
  message,
  Button,
  Layout,
} from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import AvatarRenderer from '../components/AvatarRenderer';

const { Title, Paragraph } = Typography;
const { Content } = Layout;

// Avatar shape/type
type Avatar = {
  id: string;
  name: string;
  modelUrl: string;
};

const AvatarCreatorPage = () => {
  const [avatars, setAvatars] = useState<Avatar[]>([]);
  const navigate = useNavigate();

  // Fetch avatar data on mount
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
  }, []);

  // Save avatar choice and navigate back
  const handleAvatarSelect = (avatar: Avatar): void => {
    localStorage.setItem('selectedAvatar', JSON.stringify(avatar));
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

        <Row gutter={[24, 24]}>
          {avatars.map((avatar) => (
            <Col xs={24} sm={12} lg={6} key={avatar.id}>
              <Card
                title={avatar.name}
                hoverable
                onClick={() => handleAvatarSelect(avatar)}
                style={{ height: '100%', cursor: 'pointer' }}
              >
                <div style={{ height: '600px' }}>
                  <AvatarRenderer
                    avatarUrl={avatar.modelUrl}
                    cameraType="full"
                  />
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      </Content>
    </Layout>
  );
};

export default AvatarCreatorPage;
