/**
 * TeacherLayout.tsx
 * Page frame for the teacher dashboard: header with Class / Words navigation and a centred content column.
 */

import React from "react";
import { Button, Layout, Segmented, Space, Typography } from "antd";
import { HomeOutlined } from "@ant-design/icons";
import { useLocation, useNavigate } from "react-router-dom";

interface TeacherLayoutProps {
  children: React.ReactNode;
}

const TeacherLayout: React.FC<TeacherLayoutProps> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const section = location.pathname.startsWith("/teacher/words")
    ? "words"
    : "class";

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Layout.Header
        style={{
          background: "#fff",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          padding: "0 16px",
          borderBottom: "1px solid #f0f0f0",
          flexWrap: "wrap",
          height: "auto",
          minHeight: 64,
        }}
      >
        <Space size={12} wrap>
          <Typography.Title level={4} style={{ margin: 0 }}>
            Teacher dashboard
          </Typography.Title>
          <Segmented
            value={section}
            onChange={(value) =>
              navigate(value === "words" ? "/teacher/words" : "/teacher")
            }
            options={[
              { label: "My class", value: "class" },
              { label: "Words", value: "words" },
            ]}
          />
        </Space>
        <Button icon={<HomeOutlined />} onClick={() => navigate("/")}>
          KIVA home
        </Button>
      </Layout.Header>
      <Layout.Content style={{ padding: 16 }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>{children}</div>
      </Layout.Content>
    </Layout>
  );
};

export default TeacherLayout;
