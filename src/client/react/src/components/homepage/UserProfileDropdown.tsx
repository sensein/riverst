import React, { useEffect, useState, useRef } from 'react';
import { Dropdown, Avatar, Spin, message } from 'antd';
import {
  UserOutlined,
  SettingOutlined,
  HistoryOutlined,
  LogoutOutlined,
  TeamOutlined
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { hasRole } from '../../utils/roles';
import { LoadingOutlined } from '@ant-design/icons';

const UserProfileDropdown: React.FC = () => {
  const navigate = useNavigate();
  const { user, logout, authRequest } = useAuth();
  console.log(" UserProfileDropdown user:", user);
  const [sessions, setSessions] = useState<object[]>([]);
  const isResearcher = hasRole(user, 'researcher');
  const isTeacher = hasRole(user, 'teacher');
  const [loading, setLoading] = useState(isResearcher);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const [version, setVersion] = useState<string | null>(null);

  useEffect(() => {
    authRequest.get('/api/kiva/version').then(r => setVersion(r.data?.version || null)).catch(() => {});
  }, [authRequest]);
  // "v2.0.1" -> "V2.0.1"; leave commit-hash fallbacks (local dev) as-is.
  const versionLabel = version && /\d+\.\d+/.test(version) ? 'V' + version.replace(/^v/i, '') : version;

  useEffect(() => {
    // Raw session history is for researchers only; teacher-only accounts would get a 403.
    if (!isResearcher) {
      setLoading(false);
      return;
    }
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
  }, [isResearcher]);

  const handleLogout = () => {
    logout();
    message.success('Successfully logged out');
    navigate('/login');
  };

  const menuItems = [
    {
      key: 'user-info',
      label: (
        <span>
          {user?.name || 'User'}
          {versionLabel && <span style={{ marginLeft: 8, fontSize: 11, fontWeight: 600, color: '#2656d8' }}>{versionLabel}</span>}
        </span>
      ),
      icon: <UserOutlined />,
      disabled: true
    },
    {
      type: 'divider' as const
    },
    ...(isTeacher
      ? [
          {
            key: 'teacher',
            label: 'Teacher dashboard',
            icon: <TeamOutlined />,
            onClick: () => navigate('/teacher')
          }
        ]
      : []),
    ...(isResearcher
      ? [
          {
            key: 'history',
            label: 'History',
            icon: <HistoryOutlined />,
            disabled: loading || sessions.length === 0,
            onClick: () => {
              if (sessions.length > 0) navigate('/sessions');
            }
          }
        ]
      : []),
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
