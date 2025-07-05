import { Link } from 'react-router-dom';
import React from 'react';
import { Card, Carousel, Typography, Tag } from 'antd';
import './ActivityCard.css';

const { Paragraph } = Typography;

interface ActivityCardProps {
  title: string;
  images: string[];
  description: string;
  route: string;
  disabled?: boolean;
  settings_options_filepath?: string;
}

const ActivityCard: React.FC<ActivityCardProps> = ({
  title,
  images,
  description,
  route,
  disabled = false,
  settings_options_filepath,
}) => {
  const cardContent = (
    <div
      className="activity-card-container"
      style={{
        position: 'relative',
        opacity: disabled ? 0.6 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
        pointerEvents: disabled ? 'none' : 'auto',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {disabled && (
        <Tag
          color="gold"
          style={{
            position: 'absolute',
            top: 10,
            right: 10,
            zIndex: 1,
            fontWeight: 'bold',
          }}
        >
          Coming Soon
        </Tag>
      )}
      <Card
        style={{
          height: '100%', 
          borderRadius: 12,
          overflow: 'hidden',
          boxShadow: '0 2px 10px rgba(0, 0, 0, 0.06)',
          flexGrow: 1,
          display: 'flex',
          flexDirection: 'column',
        }}
        title={title}
        className="activity-card-body"
      >
        <div className="carousel-container">
          <Carousel autoplay autoplaySpeed={2000} arrows={false} dots={false}>
            {images.map((img, idx) => (
              <div key={idx} className="image-container">
                <img src={img} alt={`${title}-${idx}`} className="activity-image" />
              </div>
            ))}
          </Carousel>
        </div>
        <Paragraph style={{ fontSize: 16, textAlign: 'left' }}>{description}</Paragraph>
      </Card>
    </div>
  );

  return disabled ? (
    <div>{cardContent}</div>
  ) : (
    <Link
      to={route}
      state={settings_options_filepath ? { settingsUrl: settings_options_filepath } : undefined}
      style={{ textDecoration: 'none', height: '100%', display: 'block' }}
    >
      {cardContent}
    </Link>
  );
};

export default ActivityCard;
