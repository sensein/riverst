/**
 * StatusTag.tsx
 * Coloured tag for a student's class status.
 */

import React from "react";
import { Tag } from "antd";
import { STATUS_LABELS } from "./labels";

const COLORS: Record<string, string> = {
  on_track: "green",
  needs_attention: "orange",
  inactive: "default",
  no_sessions: "default",
  archived: "default",
};

const StatusTag: React.FC<{ status: string }> = ({ status }) => (
  <Tag color={COLORS[status] ?? "default"}>
    {STATUS_LABELS[status] ?? status}
  </Tag>
);

export default StatusTag;
