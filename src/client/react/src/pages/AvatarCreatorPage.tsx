import { useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import AvatarRenderer from '../components/AvatarRenderer';

const API_URL = 'http://localhost:8000/health';

const avatars = [
  {
    id: 'avatar1',
    name: 'Ava',
    modelUrl: 'https://models.readyplayer.me/67eaadeeffcddc994a40ed15.glb?morphTargets=mouthOpen,Oculus Visemes',
    audioUrl: null,
  },
  {
    id: 'avatar2',
    name: 'Leo',
    modelUrl: 'https://models.readyplayer.me/67f5673ac9f387ddee751927.glb?morphTargets=mouthOpen,Oculus Visemes',
    audioUrl: null,
  },
  {
    id: 'avatar3',
    name: 'Maya',
    modelUrl: 'https://models.readyplayer.me/67f5675a94c0a90f22341c86.glb?morphTargets=mouthOpen,Oculus Visemes',
    audioUrl: null,
  },
];

const AvatarCreatorPage = () => {
  const navigate = useNavigate();

  const handleAvatarSelect = async (avatarUrl: string) => {
    try {
      await axios.post('http://localhost:7860/avatar', { avatar_url: avatarUrl });
      navigate('/');
    } catch (error) {
      console.error('Failed to send avatar to server:', error);
    }
  };

  const playVoice = (audioUrl: string) => {
    const audio = new Audio(audioUrl);
    audio.play();
  };

  return (
    <div className="p-6 space-y-6">
        <h1 className="text-3xl font-bold">Avatar creator</h1>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {avatars.map((avatar) => (
            <div key={avatar.id} className="border rounded-lg p-4 shadow">
                <h2 className="text-xl font-semibold mb-4 text-center">{avatar.name}</h2>
                <div className="w-full h-64">
                <AvatarRenderer avatarUrl={avatar.modelUrl} cameraType='headshot'/>
                </div>
                <div className="flex justify-between mt-4">
                { avatar.audioUrl && <button
                    className="bg-blue-500 text-white px-4 py-2 rounded"
                    onClick={() => playVoice(avatar.audioUrl)}
                >
                    Play Voice
                </button>}
                <button
                    className="bg-green-600 text-white px-4 py-2 rounded"
                    onClick={() => handleAvatarSelect(avatar.modelUrl)}
                >
                    Select
                </button>
                </div>
            </div>
            ))}
        </div>
    </div>
  );
};

export default AvatarCreatorPage;
