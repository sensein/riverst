import React from 'react';
import { Button, Layout, Space } from 'antd';
import { TeamOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import UserProfileDropdown from './UserProfileDropdown';
import { useAuth } from '../../contexts/AuthContext';
import { hasRole } from '../../utils/roles';
import './Navbar.css';

const Navbar: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

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
        <UserProfileDropdown />
      </Space>
    </Layout.Header>
  );
};

export default Navbar;
