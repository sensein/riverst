/**
 * StepOutcome.tsx
 * One teaching step with its result: done, tried but not yet, or not reached.
 */

import React from "react";
import { Space, Typography } from "antd";
import {
  CheckCircleFilled,
  ExclamationCircleFilled,
  MinusCircleOutlined,
} from "@ant-design/icons";
import { STEP_LABELS, STEP_RESULT_LABELS } from "./labels";
import type { StepResult } from "./types";

const ICONS: Record<string, React.ReactNode> = {
  completed: <CheckCircleFilled style={{ color: "#52c41a" }} />,
  attempted_not_completed: (
    <ExclamationCircleFilled style={{ color: "#fa8c16" }} />
  ),
  not_reached: <MinusCircleOutlined style={{ color: "#bfbfbf" }} />,
};

interface StepOutcomeProps {
  step: string;
  result: StepResult;
}

const StepOutcome: React.FC<StepOutcomeProps> = ({ step, result }) => (
  <Space
    align="start"
    style={{ width: "100%", justifyContent: "space-between" }}
  >
    <Space>
      {result ? (
        ICONS[result]
      ) : (
        <MinusCircleOutlined style={{ color: "#d9d9d9" }} />
      )}
      <Typography.Text>{STEP_LABELS[step]}</Typography.Text>
    </Space>
    <Typography.Text
      type={result === "attempted_not_completed" ? "warning" : "secondary"}
    >
      {result ? STEP_RESULT_LABELS[result] : "Being prepared"}
    </Typography.Text>
  </Space>
);

export default StepOutcome;
