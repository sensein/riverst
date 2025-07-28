import React from 'react';
import { useParams } from 'react-router-dom';
import { Card, Typography, Layout } from 'antd';
import { CheckCircleOutlined } from '@ant-design/icons';

const { Content } = Layout;
const { Title, Text } = Typography;

interface SessionEndPageProps {}

const SessionEndPage: React.FC<SessionEndPageProps> = () => {
  const { sessionId } = useParams<{ sessionId: string }>();

  return (
    <Layout style={{ minHeight: '100vh', backgroundColor: '#e6f4ff' }}>
      <Content style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        padding: '20px'
      }}>
        <Card
          style={{
            maxWidth: 500,
            width: '100%',
            textAlign: 'center',
            borderRadius: 12,
            boxShadow: '0 4px 10px rgba(0, 0, 0, 0.05)',
          }}
        >
          <CheckCircleOutlined
            style={{
              fontSize: '4rem',
              color: '#1890ff',
              marginBottom: '1rem'
            }}
          />

          <Title level={2} style={{
            marginBottom: '1rem',
            color: '#1f1f1f',
            fontFamily: "'Open Sans', sans-serif"
          }}>
            Session Complete
          </Title>

          <Text style={{
            fontSize: '1.2rem',
            color: '#1f1f1f',
            fontFamily: "'Open Sans', sans-serif",
            lineHeight: '1.6'
          }}>
            Thank you for talking to Riverst! You may close this page now.
          </Text>

          {sessionId && (
            <div style={{
              marginTop: '2rem',
              padding: '1rem',
              backgroundColor: '#f0f8ff',
              borderRadius: 8,
              border: '1px solid #d6e4ff'
            }}>
              <Text style={{
                fontSize: '0.9rem',
                color: '#666',
                fontFamily: "'Open Sans', sans-serif"
              }}>
                Session ID: {sessionId}
              </Text>
            </div>
          )}
        </Card>
      </Content>
    </Layout>
  );
};

export default SessionEndPage;
