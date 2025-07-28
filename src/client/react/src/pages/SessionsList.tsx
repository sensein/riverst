import { useEffect, useState } from "react";
import {
  List,
  Typography,
  Spin,
  Layout,
  Button,
  Divider
} from "antd";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { Link, useNavigate } from "react-router-dom";
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';

const { Title, Text } = Typography;

function formatSessionId(id: string) {
  // format: user_id__20250521_165335_2f11d904
  const [userPart, rest] = id.split("__");
  if (!rest) return { user: userPart, date: "", time: "", unique: "" };

  const [datePart, timePart, uniquePart] = rest.split("_");
  if (!datePart || !timePart || !uniquePart)
    return { user: userPart, date: rest, time: "", unique: "" };

  const date = `${datePart.slice(0, 4)}-${datePart.slice(4, 6)}-${datePart.slice(6, 8)}`;
  const time = `${timePart.slice(0, 2)}:${timePart.slice(2, 4)}:${timePart.slice(4, 6)}`;
  return { user: userPart, date, time, unique: uniquePart };
}

export default function SessionsList() {
  const [sessions, setSessions] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const { authRequest } = useAuth();

  useEffect(() => {
    let isMounted = true;
    
const fetchSessions = async () => {
  try {
    const apiUrl = `${import.meta.env.VITE_API_PROTOCOL}://${import.meta.env.VITE_API_HOST}:${import.meta.env.VITE_API_PORT}/api/sessions`;
    const response = await authRequest.get(apiUrl);
    if (isMounted) setSessions(response.data);
  } catch (error) {
    console.error('Failed to fetch sessions:', error);
  } finally {
    if (isMounted) setLoading(false);
  }
}
    
    fetchSessions();
    const intervalId = setInterval(fetchSessions, 5000);
    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
  }, []);

  if (loading) return <Spin />;

  // Group by user_id
  const grouped = sessions.reduce((acc, id) => {
    const { user } = formatSessionId(id);
    if (!acc[user]) acc[user] = [];
    acc[user].push(id);
    return acc;
  }, {} as Record<string, string[]>);

  // Sort sessions in each group by date+time descending
  Object.keys(grouped).forEach((user) => {
    grouped[user].sort((a, b) => {
      const [, aRest] = a.split("__");
      const [, bRest] = b.split("__");
      return aRest.localeCompare(bRest); // Oldest first
    });
  });

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <div style={{ padding: "2rem" }}>
        <div
          style={{
            padding: "0 32px",
            marginBottom: 32,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
          }}
        >
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate("/")}
            style={{ marginRight: 16 }}
          >
            Back to Home
          </Button>
          <Title level={2} style={{ margin: 0, flex: 1, textAlign: "center" }}>
            Sessions
          </Title>
          <div style={{ width: 104 }} />
        </div>

        {Object.entries(grouped).map(([user, userSessions]) => (
          <div key={user} style={{ marginBottom: "2rem" }}>
            <Divider orientation="left">
              <Title level={4}>{user}</Title>
            </Divider>
            <List
              dataSource={userSessions}
              bordered
              renderItem={(id) => {
                const { date, time, unique } = formatSessionId(id);
                return (
                  <Link to={`/sessions/${id}`}>
                    <List.Item key={id} style={{ background: "#fff" }}>
                      <Text strong>{date}</Text>{" "}
                      <Text code>{time}</Text>{" "}
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {unique}
                      </Text>
                    </List.Item>
                  </Link>
                );
              }}
            />
          </div>
        ))}
      </div>
    </Layout>
  );
}