import React from 'react';
import { Layout } from 'antd';
import UserProfileDropdown from './UserProfileDropdown';
import './Navbar.css';
import Logo from '/logo/riverst_black.svg';

const Navbar: React.FC = () => (
  <Layout.Header className="navbar">
    <div className="navbar-logo riverst">
      <img src={Logo} alt="Riverst logo" className="navbar-logo-icon" />
      Riverst
    </div>
    <UserProfileDropdown />
  </Layout.Header>
);

export default Navbar;
