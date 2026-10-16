import React from 'react';
import { Button, Layout, Space } from 'antd';
import { TeamOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { hasRole } from '../../utils/roles';
import './Navbar.css';

const Navbar: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  // Account dropdown + version live in the WorkspaceTabShell top bar now (shown on both tabs),
  // so the Navbar keeps just the logo and the quick Teacher-dashboard shortcut.
  return (
    <Layout.Header className="navbar">
      <div className="navbar-logo riverst">
        <img src={'/logo/riverst_black.svg'} alt="Riverst logo" className="navbar-logo-icon" />
        Riverst
      </div>
      <Space size={12}>
        {hasRole(user, 'teacher') && (
          <Button icon={<TeamOutlined />} onClick={() => navigate('/teacher')}>
            Teacher dashboard
          </Button>
        )}
      </Space>
    </Layout.Header>
  );
};

export default Navbar;
