import { useNavigate } from 'react-router-dom';
import { Typography, Button, message, Layout } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import AvatarUploader from '../components/AvatarUploader';

const { Title, Paragraph } = Typography;

const AvatarUploadPage = () => {
  const navigate = useNavigate();

  const handleAvatarConfirmed = (modelUrl: string, gender: string) => {
    const avatar = { modelUrl, gender };

    // Set as the active avatar
    localStorage.setItem('selectedAvatar', JSON.stringify(avatar));

    // Persist in the user's uploaded avatars list
    const existing = localStorage.getItem('uploadedAvatars');
    const uploads: { modelUrl: string; gender: string }[] = existing ? JSON.parse(existing) : [];
    uploads.push(avatar);
    localStorage.setItem('uploadedAvatars', JSON.stringify(uploads));

    message.success('Avatar uploaded and selected');
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
          <Title level={2} style={{ marginBottom: 0 }}>Upload your avatar</Title>
          <Paragraph style={{ fontSize: '20px' }}>
            Upload a GLB avatar file to use in the app. The avatar should be a humanoid model
            with morph targets for lip sync and facial expressions.
          </Paragraph>
        </div>

        <div style={{ flexGrow: 1, overflow: 'hidden' }}>
          <AvatarUploader onAvatarConfirmed={handleAvatarConfirmed} />
        </div>
      </div>
    </Layout>
  );
};

export default AvatarUploadPage;
