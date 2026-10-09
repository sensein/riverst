/**
 * LevelTrend.tsx
 * Reading-level trend from antd primitives only: a statistic with a direction arrow and a short
 * timeline of the sessions where the level changed.
 */

import React from "react";
import { Statistic, Timeline, Typography } from "antd";
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  MinusOutlined,
} from "@ant-design/icons";
import { formatDate } from "./labels";

interface LevelTrendProps {
  trend: { session_id: string; date: string; level: number }[];
}

const levelName = (level: number): string =>
  level <= 3 ? "below Grade 4" : `Grade ${level}`;

const LevelTrend: React.FC<LevelTrendProps> = ({ trend }) => {
  if (trend.length < 2) return null;
  const first = trend[0].level;
  const last = trend[trend.length - 1].level;
  const changes = trend.filter(
    (point, i) => i === 0 || point.level !== trend[i - 1].level,
  );

  let icon = <MinusOutlined />;
  let text = "no change";
  let color: string | undefined;
  if (last > first) {
    icon = <ArrowUpOutlined />;
    text = `up from ${levelName(first)}`;
    color = "#389e0d";
  } else if (last < first) {
    icon = <ArrowDownOutlined />;
    text = `down from ${levelName(first)}`;
    color = "#d46b08";
  }

  return (
    <div>
      <Statistic
        title="Since the first estimate"
        value={text}
        prefix={icon}
        valueStyle={{ fontSize: 16, color }}
      />
      {changes.length > 1 && (
        <Timeline
          style={{ marginTop: 16, marginBottom: -24 }}
          items={changes.map((point) => ({
            children: (
              <Typography.Text>
                {formatDate(point.date)}: {levelName(point.level)}
              </Typography.Text>
            ),
          }))}
        />
      )}
    </div>
  );
};

export default LevelTrend;
