import React, { useEffect, useState, useRef } from 'react';
import { Dropdown, Avatar, Spin } from 'antd';
import {
  UserOutlined,
  SettingOutlined,
  HistoryOutlined
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

const UserProfileDropdown: React.FC = () => {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    const fetchSessions = () => {
      fetch("http://localhost:7860/api/sessions")
        .then((res) => res.json())
        .then((data) => {
          setSessions(data);
          if (data.length > 0 && intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
        })
        .catch(() => {
          setSessions([]);
        })
        .finally(() => {
          setLoading(false);
        });
    };

    fetchSessions(); // Initial fetch
    intervalRef.current = setInterval(fetchSessions, 5000); // Poll every 5s

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  const menuItems = [
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
    }
  ];

  return (
    <Dropdown
      menu={{ items: menuItems }}
      trigger={['click']}
      placement="bottomRight"
    >
      <Spin spinning={loading} size="small">
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
