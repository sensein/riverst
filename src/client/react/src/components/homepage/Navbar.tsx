import React, { useEffect, useState } from 'react';
import { Button, Layout, Space, Tag } from 'antd';
import { TeamOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import UserProfileDropdown from './UserProfileDropdown';
import { useAuth } from '../../contexts/AuthContext';
import { hasRole } from '../../utils/roles';
import './Navbar.css';

const Navbar: React.FC = () => {
  const { user, authRequest } = useAuth();
  const navigate = useNavigate();
  const [version, setVersion] = useState<string | null>(null);

  useEffect(() => {
    authRequest.get('/api/kiva/version').then(r => setVersion(r.data?.version || null)).catch(() => {});
  }, [authRequest]);

  // "v2.0.1" -> "V2.0.1"; leave commit-hash fallbacks (local dev) as-is.
  const versionLabel = version && /\d+\.\d+/.test(version) ? 'V' + version.replace(/^v/i, '') : version;

  return (
    <Layout.Header className="navbar">
      <div className="navbar-logo riverst">
        <img src={'/logo/riverst_black.svg'} alt="Riverst logo" className="navbar-logo-icon" />
        Riverst
      </div>
      <Space size={12}>
        {versionLabel && <Tag color="blue" style={{ fontWeight: 600, marginRight: 0 }}>{versionLabel}</Tag>}
        {hasRole(user, 'teacher') && (
          <Button icon={<TeamOutlined />} onClick={() => navigate('/teacher')}>
            Teacher dashboard
          </Button>
        )}
        <UserProfileDropdown />
      </Space>
    </Layout.Header>
  );
};

export default Navbar;
