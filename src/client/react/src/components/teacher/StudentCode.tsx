/**
 * StudentCode.tsx
 * A student's code in large type with "Copy link" and "Copy code" buttons.
 */

import React from "react";
import { Button, Space, Typography } from "antd";
import { CopyOutlined } from "@ant-design/icons";
import { fullStudentLink, useCopy } from "../../utils/studentCode";

const StudentCode: React.FC<{ code: string; link: string }> = ({
  code,
  link,
}) => {
  const copy = useCopy();
  return (
    <Space direction="vertical" size={8}>
      <Typography.Text
        style={{ fontFamily: "monospace", fontSize: 28, letterSpacing: 4 }}
      >
        {code}
      </Typography.Text>
      <Space wrap>
        <Button
          icon={<CopyOutlined />}
          onClick={() => copy(fullStudentLink(link), "Link")}
        >
          Copy link
        </Button>
        <Button icon={<CopyOutlined />} onClick={() => copy(code, "Code")}>
          Copy code
        </Button>
      </Space>
    </Space>
  );
};

export default StudentCode;
