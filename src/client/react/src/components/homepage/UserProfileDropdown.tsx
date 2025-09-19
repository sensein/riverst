import React, { useEffect, useState, useRef } from 'react';
import { Dropdown, Avatar, Spin, message } from 'antd';
import {
  UserOutlined,
  SettingOutlined,
  HistoryOutlined,
  LogoutOutlined
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { LoadingOutlined } from '@ant-design/icons';

const UserProfileDropdown: React.FC = () => {
  const navigate = useNavigate();
  const { user, logout, authRequest } = useAuth();
  console.log(" UserProfileDropdown user:", user);
  const [sessions, setSessions] = useState<object[]>([]);
  const [loading, setLoading] = useState(true);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    const fetchSessions = async () => {
      try {
        const response = await authRequest.get(`/api/sessions`);
        setSessions(response.data);
        if (response.data.length > 0 && intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      } catch (error) {
        console.error('Failed to fetch sessions:', error);
        setSessions([]);
      } finally {
        setLoading(false);
      }
    };

    fetchSessions(); // Initial fetch
    intervalRef.current = setInterval(fetchSessions, 5000); // Poll every 5s

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  const handleLogout = () => {
    logout();
    message.success('Successfully logged out');
    navigate('/login');
  };

  const menuItems = [
    {
      key: 'user-info',
      label: user?.name || 'User',
      icon: <UserOutlined />,
      disabled: true
    },
    {
      type: 'divider' as const
    },
    {
      key: 'history',
      label: 'History',
      icon: <HistoryOutlined />,
      disabled: loading || sessions.length === 0,
      onClick: () => {
        if (sessions.length > 0) navigate('/sessions');
      }
    },
    {
      key: 'settings',
      label: 'Settings',
      icon: <SettingOutlined />,
      disabled: true
    },
    {
      type: 'divider' as const
    },
    {
      key: 'logout',
      label: 'Logout',
      icon: <LogoutOutlined />,
      onClick: handleLogout,
      disabled: user?.email === "dev@localhost"
    }
  ];

  return (
    <Dropdown
      menu={{ items: menuItems }}
      trigger={['click']}
      placement="bottomRight"
    >
      <Spin indicator={<LoadingOutlined spin />} size='small' spinning={loading} >
        <Avatar
          style={{
            backgroundColor: '#E69F00',
            cursor: 'pointer',
            width: '40px',
            height: '40px',
            fontSize: '30px'
          }}
          icon={<UserOutlined />}
        />
      </Spin>
    </Dropdown>
  );
};

export default UserProfileDropdown;
