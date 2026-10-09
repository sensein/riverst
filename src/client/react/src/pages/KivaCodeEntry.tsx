/**
 * KivaCodeEntry.tsx
 * Entry point for students: /kiva?code=XXXXXX saves the student code and opens KIVA vocabulary practice.
 * Without a code, it asks the student to type one.
 */

import React, { useEffect } from "react";
import { Button, Card, Form, Input, Layout, Typography } from "antd";
import { useNavigate, useSearchParams } from "react-router-dom";
import { saveStudentCode } from "../utils/studentCode";

const KIVA_SETTINGS_URL = "api/activities/vocab-tutoring/session_config";

const KivaCodeEntry: React.FC = () => {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const code = params.get("code");

  const start = (value: string) => {
    saveStudentCode(value);
    navigate("/avatar-interaction-settings", {
      replace: true,
      state: { settingsUrl: KIVA_SETTINGS_URL },
    });
  };

  useEffect(() => {
    if (code) start(code);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);

  if (code) return null;

  return (
    <Layout
      style={{
        minHeight: "100vh",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
      }}
    >
      <Card style={{ maxWidth: 420, width: "100%" }}>
        <Typography.Title level={3}>Welcome to KIVA</Typography.Title>
        <Typography.Paragraph>
          Enter the student code your teacher gave you.
        </Typography.Paragraph>
        <Form
          layout="vertical"
          onFinish={({ code: typed }) => start(typed)}
          requiredMark={false}
        >
          <Form.Item
            name="code"
            label="Student code"
            normalize={(v: string) => v.toUpperCase()}
            rules={[
              { required: true, message: "Enter your student code." },
              { len: 6, message: "Codes have 6 characters." },
            ]}
          >
            <Input
              autoFocus
              maxLength={6}
              style={{
                fontFamily: "monospace",
                fontSize: 20,
                letterSpacing: 4,
              }}
            />
          </Form.Item>
          <Button type="primary" htmlType="submit" block>
            Start
          </Button>
        </Form>
      </Card>
    </Layout>
  );
};

export default KivaCodeEntry;
