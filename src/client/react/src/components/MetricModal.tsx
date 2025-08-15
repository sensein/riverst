/**
 * MetricModal.tsx
 * Modal component for displaying session metrics.
 */

import React from "react";
import {
  Modal,
  Collapse,
  Tooltip,
  Table,
  Button,
  Typography,
} from "antd";
import {
  InfoCircleOutlined,
  BarChartOutlined,
  CodeOutlined,
} from "@ant-design/icons";

const { Paragraph } = Typography;
const { Panel } = Collapse;

// Tooltip info descriptions per metric type
const METRIC_TYPE_INFO: Record<string, string> = {
  TTFBMetricsData: "Time to first byte (TTFB) — time until the service starts responding.",
  ProcessingMetricsData: "Processing time — total time taken to fully process the input.",
  LLMUsageMetricsData: "Token usage information for LLM calls.",
  TTSUsageMetricsData: "Character count usage for text-to-speech generation.",
};

// Format numeric values
const pretty = (v: number | null) =>
  typeof v === "number" ? v.toFixed(3) : v == null ? "–" : String(v);

// Metric table data structure
type MetricStats = {
  count?: number | null;
  sum?: number | null;
  avg?: number | null;
  std?: number | null;
  min?: number | null;
  max?: number | null;
};

type MetricValue = MetricStats | Record<string, MetricStats>;
type MetricBlock = { value?: MetricValue } | MetricValue;
type ProcessorMetrics = Record<string, MetricBlock>;

type MetricsType = {
  processors:
    | Record<string, ProcessorMetrics>
    | { summary?: { timestamp?: string; processors?: Record<string, ProcessorMetrics> } };
};

// Convert stats into table rows
function flattenStats(stats: Record<string, MetricStats>) {
  return Object.entries(stats).map(([metric, value]) => ({
    metric,
    count: pretty(value.count ?? null),
    sum: pretty(value.sum ?? null),
    avg: pretty(value.avg ?? null),
    std: pretty(value.std ?? null),
    min: pretty(value.min ?? null),
    max: pretty(value.max ?? null),
  }));
}

// Metric table component
const MetricTable: React.FC<{ data: Record<string, MetricStats> }> = ({ data }) => {
  const rows = flattenStats(data);
  const statKeys = ["count", "sum", "avg", "std", "min", "max"];
  const visibleStats = statKeys.filter((key) =>
    rows.some((row) => row[key as keyof typeof row] !== undefined)
  );

  const columns = [
    { title: "Metric", dataIndex: "metric", key: "metric" },
    ...visibleStats.map((s) => ({
      title: s.charAt(0).toUpperCase() + s.slice(1),
      dataIndex: s,
      key: s,
    })),
  ];

  return (
    <Table
      size="small"
      columns={columns}
      dataSource={rows}
      pagination={false}
      rowKey="metric"
      scroll={{ x: "max-content" }}
    />
  );
};

// Main modal component
const MetricModal: React.FC<{
  open: boolean;
  onClose: () => void;
  metrics: MetricsType | null;
}> = ({ open, onClose, metrics }) => {
  const [showRaw, setShowRaw] = React.useState(false);

  const rawProcessors =
    metrics?.processors?.summary?.processors ??
    (metrics?.processors as Record<string, ProcessorMetrics>) ??
    null;

  if (!rawProcessors) {
    return (
      <Modal open={open} onCancel={onClose} footer={null} title="Session Metrics">
        <Paragraph>No metrics available.</Paragraph>
      </Modal>
    );
  }

  // Render each processor panel
  const processorPanels = Object.entries(rawProcessors).map(
    ([processorName, metricGroups]) => (
      <Panel
        key={processorName}
        header={
          <span>
            <BarChartOutlined /> {processorName}
          </span>
        }
      >
        <Collapse accordion>
          {Object.entries(metricGroups).map(([metricType, block]) => {
            const value = (block as any).value ?? block;
            const info = METRIC_TYPE_INFO[metricType];

            let tableData: Record<string, MetricStats>;

            if (metricType === "TTSUsageMetricsData") {
              tableData = { TTSUsage: value as MetricStats };
            } else if (metricType === "LLMUsageMetricsData") {
              tableData = value as Record<string, MetricStats>;
            } else {
              tableData = { [metricType]: value as MetricStats };
            }

            return (
              <Panel
                key={metricType}
                header={
                  <span>
                    {metricType.replace("MetricsData", "")}
                    {info && (
                      <Tooltip title={info}>
                        <InfoCircleOutlined style={{ marginLeft: 8 }} />
                      </Tooltip>
                    )}
                  </span>
                }
              >
                <MetricTable data={tableData} />
              </Panel>
            );
          })}
        </Collapse>
      </Panel>
    )
  );

  return (
    <Modal
      open={open}
      onCancel={() => {
        setShowRaw(false);
        onClose();
      }}
      footer={null}
      title="Session Performance Metrics"
      width={900}
      styles={{
        body: {
          maxHeight: "80vh",
          overflowY: "auto",
          padding: 24,
        },
      }}
    >
      <Collapse accordion>{processorPanels}</Collapse>

      <Button
        icon={<CodeOutlined />}
        size="small"
        style={{ marginTop: 16 }}
        onClick={() => setShowRaw((v) => !v)}
      >
        {showRaw ? "Hide Raw JSON" : "Show Raw JSON"}
      </Button>

      {showRaw && (
        <pre
          style={{
            whiteSpace: "pre-wrap",
            fontSize: 11,
            background: "#f8f8f8",
            padding: 12,
            marginTop: 12,
            borderRadius: 4,
            maxHeight: 300,
            overflow: "auto",
          }}
        >
          {JSON.stringify(metrics, null, 2)}
        </pre>
      )}
    </Modal>
  );
};

export default MetricModal;
