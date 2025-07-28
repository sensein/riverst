import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Typography, Button, message, Layout } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import AdvancedAvatarCreator from '../components/AdvancedAvatarCreator';

const { Title, Paragraph } = Typography;

const AdvancedAvatarCreatorPage = () => {
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleAvatarCreated = async (url: string, gender: string) => {
    console.log("Avatar URL:", url);
    console.log("Avatar gender:", gender);
    setAvatarUrl(url);
    localStorage.setItem('selectedAvatar', JSON.stringify({
      'modelUrl': url,
      'gender': gender
     }));
     // TODO: is it possible to get the avatar gender from the url?
    console.log("localStorage:", localStorage.getItem('selectedAvatar'));
    message.success(`Avatar selected`);
    navigate('/');
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <div
        style={{
          height: '100vh',
          display: 'flex',
          flexDirection: 'column',
          padding: '2rem',
          boxSizing: 'border-box',
        }}
      >
        <div style={{ marginBottom: '1rem' }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/')}>
            Back
          </Button>
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <Title level={2} style={{ marginBottom: 0 }}>Create your custom avatar</Title>
          <Paragraph style={{ fontSize: '20px' }}>
            Use the controls below to generate a personalized avatar to use in the app.
          </Paragraph>
        </div>

        <div style={{ flexGrow: 1, overflow: 'hidden' }}>
          {!avatarUrl && (
            <div style={{ height: '100%' }}>
              <AdvancedAvatarCreator onAvatarCreated={handleAvatarCreated} />
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
};

export default AdvancedAvatarCreatorPage;
