import React, { useState } from 'react';
import { Dropdown, Avatar, Modal, Input } from 'antd';
import { UserOutlined, SettingOutlined, HistoryOutlined, EditOutlined } from '@ant-design/icons';
import { getUserId, setUserId as persistUserId } from '../../utils/userId';
import { useNavigate } from 'react-router-dom';
const UserProfileDropdown: React.FC = () => {
  const [userId, setUserIdState] = useState<string>(getUserId());
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [newUserId, setNewUserId] = useState(userId);
  const navigate = useNavigate();

  const handleOk = () => {
    persistUserId(newUserId);
    setUserIdState(newUserId);
    setIsModalVisible(false);
  };

  const menuItems = [
    {
      key: 'userId',
      label: `ID: ${userId}`,
      icon: <UserOutlined />,
      disabled: true
    },
    {
      key: 'edit',
      label: 'Edit ID',
      icon: <EditOutlined />,
      onClick: () => setIsModalVisible(true),
    },
    {
      key: 'history',
      label: 'History',
      icon: <HistoryOutlined />,
      disabled: false,
      onClick: () => {
        // Handle history action here
        navigate('/sessions');
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
    <>
      <Dropdown
        menu={{ items: menuItems }}
        trigger={['click']}
        placement="bottomRight"
      >
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
      </Dropdown>

      <Modal
        title="Edit User ID"
        open={isModalVisible}
        onOk={handleOk}
        onCancel={() => setIsModalVisible(false)}
      >
        <Input
          maxLength={30}
          value={newUserId}
          onChange={(e) => setNewUserId(e.target.value)}
        />
      </Modal>
    </>
  );
};

export default UserProfileDropdown;
