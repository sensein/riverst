import AdvancedAvatarCreator from '../components/AdvancedAvatarCreator';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';

const AdvancedAvatarCreatorPage = () => {
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleAvatarCreated = async (url: string) => {
    setAvatarUrl(url);
    // console.log('Avatar created:', url);
    try {
      await axios.post('http://localhost:7860/avatar', { avatar_url: url });
    } catch (error) {
      console.error('Failed to save avatar to server:', error);
    }
    navigate('/');
  };

  return (
    <div style={{ height: '100vh', padding: 20 }}>
      {/* Back button */}
      <button onClick={() => navigate('/')} style={{ marginBottom: 20 }}>
        ← Back to Home
      </button>

      {!avatarUrl && (
        <AdvancedAvatarCreator onAvatarCreated={handleAvatarCreated} />
      )}
      {avatarUrl && (
        <div>
          <h2>Avatar Created ✅</h2>
          <p>{avatarUrl}</p>
          <img src={avatarUrl} alt='Avatar' style={{ width: 300 }} />
        </div>
      )}
    </div>
  );
};

export default AdvancedAvatarCreatorPage;
