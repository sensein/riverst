import React, { useEffect, useState } from 'react';
import { Layout, Spin, Alert } from 'antd';
import axios from 'axios';
import Navbar from '../components/homepage/Navbar';
import GroupedActivitySection from '../components/homepage/GroupedActivitySection';
import { Content } from 'antd/es/layout/layout';

interface Activity {
  title: string;
  images: string[];
  description: string;
  route: string;
  disabled?: boolean;
}

interface ActivityGroup {
  title: string;
  activities: Activity[];
}

const Homepage: React.FC = () => {
  const [groups, setGroups] = useState<ActivityGroup[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    axios
      .get<ActivityGroup[]>(`/api/activities`)
      .then((response) => {
        setGroups(response.data);
        setError(null);
      })
      .catch((err) => {
        console.error(err);
        setError('Failed to load activities. Please try again later.');
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Navbar />
      <Content style={{ padding: '1% 1%' }}>
        {loading && <Spin />}
        {error && <Alert type="error" message={error} showIcon />}
        {groups && (
          <div>
            <div style={{ paddingLeft: 24 }}>
              <h1 style={{ fontSize: 28, fontWeight: 700 }}>Welcome to <span className='riverst'>Riverst</span>!</h1>
              <p style={{ fontSize: 20 }}>
                <span className='riverst'>Riverst</span> is your personalized hub for interactive experiences. <u>Start by selecting one of the available activities below.</u>
              </p>
            </div>
            <GroupedActivitySection groups={groups} />
          </div>
        )}
      </Content>
    </Layout>
  );
};

export default Homepage;
