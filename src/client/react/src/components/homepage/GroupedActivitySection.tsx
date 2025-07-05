import React, { useState } from 'react';
import { Collapse, Typography, Row, Col } from 'antd';
import type { CollapseProps } from 'antd';
import ActivityCard from './ActivityCard';
import './GroupedActivitySection.css';

const { Title } = Typography;

interface Activity {
  title: string;
  images: string[];
  description: string;
  route: string;
  disabled?: boolean;
  settings_options_filepath?: string;
}

interface ActivityGroup {
  title: string;
  activities: Activity[];
}

interface Props {
  groups: ActivityGroup[];
}

const GroupedActivitySection: React.FC<Props> = ({ groups }) => {
  const [activeKey, setActiveKey] = useState<string>('1');

  const items: CollapseProps['items'] = groups.map((group, index) => ({
    key: String(index + 1),
    label: (
      <Title level={3} style={{ margin: 0 }}>
        {group.title}
      </Title>
    ),
    children: (
      <Row gutter={[16, 16]} justify="start" align="top">
        {group.activities.map((activity, idx) => (
          <Col key={idx} xs={24} sm={12} md={8} lg={6} xl={6}>
            <ActivityCard {...activity} />
          </Col>
        ))}
      </Row>
    ),
  }));

  const handleChange = (key: string | string[] | undefined) => {
    if (key === undefined || key === activeKey) return;
    if (typeof key === 'string') setActiveKey(key);
    else if (Array.isArray(key) && typeof key[0] === 'string') setActiveKey(key[0]);
  };

  return (
    <div className="activity-section">
      <Collapse
        size="large"
        accordion
        bordered={false}
        expandIconPosition="start"
        activeKey={activeKey}
        onChange={handleChange}
        items={items}
      />
    </div>
  );
};

export default GroupedActivitySection;
