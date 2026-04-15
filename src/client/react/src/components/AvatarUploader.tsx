import React, { useState, useCallback } from 'react';
import { Upload, Button, Radio, Typography, Space, Alert } from 'antd';
import { InboxOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { useAuth } from '../contexts/AuthContext';
import AvatarRenderer from './AvatarRenderer';

const { Dragger } = Upload;
const { Text } = Typography;

interface AvatarUploaderProps {
  onAvatarConfirmed: (modelUrl: string, gender: string) => void;
}

const AvatarUploader: React.FC<AvatarUploaderProps> = ({ onAvatarConfirmed }) => {
  const { authRequest } = useAuth();
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [gender, setGender] = useState<string>('masculine');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleBeforeUpload = useCallback((file: File) => {
    setError(null);

    if (!file.name.toLowerCase().endsWith('.glb')) {
      setError('Please select a .glb file.');
      return false;
    }

    if (file.size > 50 * 1024 * 1024) {
      setError('File is too large. Maximum size is 50 MB.');
      return false;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      const buffer = e.target?.result as ArrayBuffer;
      const header = new Uint8Array(buffer.slice(0, 4));
      const magic = String.fromCharCode(...header);
      if (magic !== 'glTF') {
        setError('Invalid GLB file. The file does not have a valid glTF header.');
        return;
      }

      const objectUrl = URL.createObjectURL(file);
      setSelectedFile(file);
      setPreviewUrl(objectUrl);
    };
    reader.readAsArrayBuffer(file.slice(0, 12));

    return false;
  }, []);

  const handleConfirm = async () => {
    if (!selectedFile) return;

    setUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('gender', gender);

      const response = await authRequest.post('/api/upload-avatar', formData);
      onAvatarConfirmed(response.data.modelUrl, gender);
    } catch (err: any) {
      setError(err.message || 'Failed to upload avatar.');
    } finally {
      setUploading(false);
    }
  };

  const handleReset = () => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setSelectedFile(null);
    setPreviewUrl(null);
    setError(null);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: '1rem' }}>
      {!previewUrl ? (
        <div>
          <Dragger
            accept=".glb"
            multiple={false}
            showUploadList={false}
            beforeUpload={handleBeforeUpload}
            style={{ padding: '2rem' }}
          >
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">
              Click or drag a .glb avatar file to this area
            </p>
            <p className="ant-upload-hint">
              Supports humanoid GLB avatars with ARKit blendshapes and Oculus Viseme morph targets.
              Maximum file size: 50 MB.
            </p>
          </Dragger>

          {error && (
            <Alert
              type="error"
              message={error}
              showIcon
              style={{ marginTop: '1rem' }}
              closable
              onClose={() => setError(null)}
            />
          )}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', flexGrow: 1, gap: '1rem' }}>
          <div style={{
            flexGrow: 1,
            minHeight: '400px',
            border: '1px solid #d9d9d9',
            borderRadius: '8px',
            overflow: 'hidden',
          }}>
            <AvatarRenderer avatarUrl={previewUrl} cameraType="full" />
          </div>

          <div>
            <Text strong>Select avatar body type (used for animation style):</Text>
            <div style={{ marginTop: '0.5rem' }}>
              <Radio.Group
                value={gender}
                onChange={(e) => setGender(e.target.value)}
                optionType="button"
                buttonStyle="solid"
              >
                <Radio.Button value="masculine">Masculine</Radio.Button>
                <Radio.Button value="feminine">Feminine</Radio.Button>
              </Radio.Group>
            </div>
          </div>

          {error && (
            <Alert
              type="error"
              message={error}
              showIcon
              closable
              onClose={() => setError(null)}
            />
          )}

          <Space>
            <Button onClick={handleReset} disabled={uploading}>
              Choose a different file
            </Button>
            <Button
              type="primary"
              icon={<CheckCircleOutlined />}
              onClick={handleConfirm}
              loading={uploading}
            >
              Confirm & Upload
            </Button>
          </Space>
        </div>
      )}
    </div>
  );
};

export default AvatarUploader;
