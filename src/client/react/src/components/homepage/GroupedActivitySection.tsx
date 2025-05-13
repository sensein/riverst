import React, { useState } from 'react';
import { Collapse, Typography } from 'antd';
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
      <div className="activity-inline-wrapper">
        {group.activities.map((activity, idx) => (
          <div key={idx} className="activity-inline-card">
            <ActivityCard {...activity} />
          </div>
        ))}
      </div>
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
