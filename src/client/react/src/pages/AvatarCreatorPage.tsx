import { useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { Row, Col, Card, Typography, message, Button, Layout } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import AvatarRenderer from '../components/avatarInteraction/AvatarRenderer';

const { Title } = Typography;

type Avatar = {
  id: string;
  name: string;
  modelUrl: string;
};

const AvatarCreatorPage = () => {
  const [avatars, setAvatars] = useState<Avatar[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchAvatars = async () => {
      try {
        const response = await axios.get(`${import.meta.env.VITE_API_PROTOCOL}://${import.meta.env.VITE_API_HOST}:${import.meta.env.VITE_API_PORT}/api/avatars`);
        setAvatars(response.data);
      } catch (error) {
        console.error('Failed to fetch avatars:', error);
        message.error('Could not load avatars.');
      }
    };

    fetchAvatars();
  }, []);

  const handleAvatarSelect = (avatar: Avatar): void => {
    localStorage.setItem('selectedAvatar', JSON.stringify(avatar));
    console.log('Selected Avatar:', localStorage.getItem('selectedAvatar'));
    message.success(`Avatar selected`);
    navigate('/');
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <div style={{ padding: '2rem' }}>
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/')}
          style={{ marginBottom: '1rem' }}
        >
          Back
        </Button>

        <Title level={2}>Pick your avatar</Title>
        <p style={{ fontSize: '20px', fontFamily: 'Open Sans, sans-serif' }}>
          Choose an avatar to interact with in the app. Click on an avatar to select it.
        </p>

        <Row gutter={[24, 24]}>
          {avatars.map((avatar) => (
            <Col xs={24} sm={12} lg={8} key={avatar.id}>
              <Card
                title={avatar.name}
                hoverable
                onClick={() => handleAvatarSelect(avatar)}
                style={{ cursor: 'pointer' }}
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
      </div>
    </Layout>
  );
};

export default AvatarCreatorPage;
