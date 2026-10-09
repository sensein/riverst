/**
 * ReadingLevel.tsx
 * Shows the displayed reading level, marks teacher-set levels, and optionally the automatic estimate.
 */

import React from "react";
import { Space, Tag, Typography } from "antd";
import type { ReadingLevel as Level } from "./types";

interface ReadingLevelProps {
  level: Level;
  /** The automatic estimate, shown alongside when the teacher has set a different level. */
  estimate?: Level;
}

const ReadingLevel: React.FC<ReadingLevelProps> = ({ level, estimate }) => (
  <Space size={4} wrap>
    <span>{level.label}</span>
    {level.source === "teacher" && <Tag color="blue">set by teacher</Tag>}
    {level.source === "teacher" &&
      estimate &&
      estimate.label !== level.label && (
        <Typography.Text type="secondary">
          (estimate: {estimate.label})
        </Typography.Text>
      )}
  </Space>
);

export default ReadingLevel;
