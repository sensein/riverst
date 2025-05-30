// src/pages/SessionsList.jsx
import React, { useEffect, useState } from "react";
import { List, Card, Typography, Spin, Layout, Button } from "antd";
import { InfoCircleOutlined, ArrowLeftOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
const { Title, Text } = Typography;
import { useParams, useNavigate } from "react-router-dom";

function formatSessionId(id) {
  // Expected format: 20250521_165335_2f11d904
  const [datePart, timePart, uniquePart] = id.split("_");
  if (!datePart || !timePart || !uniquePart) return { date: id, time: "", unique: "" };

  // Format date: 20250521 -> 2025-05-21
  const date = `${datePart.slice(0, 4)}-${datePart.slice(4, 6)}-${datePart.slice(6, 8)}`;
  // Format time: 165335 -> 16:53:35
  const time = `${timePart.slice(0, 2)}:${timePart.slice(2, 4)}:${timePart.slice(4, 6)}`;
  return { date, time, unique: uniquePart };
}

export default function SessionsList() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    let isMounted = true;
    let intervalId;

    const fetchSessions = () => {
      fetch("http://localhost:7860/api/sessions")
        .then((res) => res.json())
        .then((data) => {
          if (isMounted) setSessions(data);
        })
        .finally(() => {
          if (isMounted) setLoading(false);
        });
    };

    fetchSessions();
    intervalId = setInterval(fetchSessions, 5000); // Poll every 5 seconds

    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
  }, []);

  if (loading) return <Spin />;

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <div style={{ padding: "2rem"}}>
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
          <Title level={2} style={{ margin: 0, flex: 1, textAlign: "center" }}>Sessions</Title>
          <div style={{ width: 104 }} /> {/* Spacer to match Back button width */}
        </div>
        <List
          dataSource={sessions}
          bordered
          renderItem={id => {
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
    </Layout>
  );
}
