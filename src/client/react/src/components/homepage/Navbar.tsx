import React from 'react';
import { Layout } from 'antd';
import UserProfileDropdown from './UserProfileDropdown';
import './Navbar.css';

const Navbar: React.FC = () => (
  <Layout.Header className="navbar">
    <div className="navbar-logo riverst">
      <img src={'/logo/riverst_black.svg'} alt="Riverst logo" className="navbar-logo-icon" />
      Riverst
    </div>
    <UserProfileDropdown />
  </Layout.Header>
);

export default Navbar;
