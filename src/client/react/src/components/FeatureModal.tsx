/**
 * FeatureModal.tsx
 * Modal component for displaying session features.
 */

import React from "react";
import {
  Modal,
  Collapse,
  Tooltip,
  Table,
  Button,
} from "antd";
import {
  InfoCircleOutlined,
  BarChartOutlined,
  CodeOutlined,
} from "@ant-design/icons";

const { Panel } = Collapse;

// Section definitions
type SectionKey =
  | "opensmile"
  | "praat_parselmouth"
  | "torchaudio_squim"
  | "embeddings";

const SECTION_INFO: Record<SectionKey, { title: string; info: string }> = {
  opensmile: {
    title: "OpenSMILE Features",
    info: "Standard acoustic features used in voice analysis, e.g., pitch, loudness, MFCCs, etc.",
  },
  praat_parselmouth: {
    title: "Praat/Parselmouth Features",
    info: "Speech and phonetic features extracted using Praat via Parselmouth, such as pitch, pauses, jitter, shimmer.",
  },
  torchaudio_squim: {
    title: "Speech Quality Metrics (torchaudio SQUIM)",
    info: "Objective speech quality metrics, such as STOI, PESQ, SI-SDR.",
  },
  embeddings: {
    title: "Speaker Embeddings",
    info: "Vector representation (embedding) capturing speaker characteristics.",
  },
};

// Format number values
const pretty = (v: number | null) =>
  typeof v === "number" ? v.toFixed(4) : v == null ? "–" : String(v);

// Convert feature object to table data
function featuresToTableData(obj: Record<string, number | null | undefined>) {
  return Object.entries(obj).map(([key, value]) => ({
    key,
    value: pretty(value ?? null),
  }));
}

// Component props
interface FeatureModalProps {
  open: boolean;
  onClose: () => void;
  features: Partial<Record<SectionKey, Record<string, number> | number[]>> | null;
}

const FeatureModal: React.FC<FeatureModalProps> = ({ open, onClose, features }) => {
  const [showEmbedding, setShowEmbedding] = React.useState(false);

  if (!features) {
    return (
      <Modal
        open={open}
        onCancel={onClose}
        footer={null}
        title="Audio Features"
        destroyOnHidden
      >
        <p>No feature data available.</p>
      </Modal>
    );
  }

  const panels = (Object.keys(SECTION_INFO) as SectionKey[]).map((k) => {
    if (!(k in features)) return null;

    // Embedding-specific display logic
    if (k === "embeddings") {
      const arr = features.embeddings as number[] | undefined;
      if (!arr) return null;

      const mean = arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : null;
      const std =
        arr.length > 0
          ? Math.sqrt(arr.reduce((a, b) => a + Math.pow(b - (mean ?? 0), 2), 0) / arr.length)
          : null;

      return (
        <Panel
          key={k}
          header={
            <span>
              <BarChartOutlined /> {SECTION_INFO[k].title}
              <Tooltip title={SECTION_INFO[k].info}>
                <InfoCircleOutlined style={{ marginLeft: 8 }} />
              </Tooltip>
            </span>
          }
        >
          <div style={{ marginBottom: 8 }}>
            <b>Length:</b> {arr.length}{"  |  "}
            <b>Mean:</b> {pretty(mean)}{"  |  "}
            <b>Std:</b> {pretty(std)}
          </div>
          <Button
            size="small"
            icon={<CodeOutlined />}
            onClick={() => setShowEmbedding((v) => !v)}
            style={{ marginBottom: 8 }}
          >
            {showEmbedding ? "Hide Raw Vector" : "Show Raw Vector"}
          </Button>
          {showEmbedding && (
            <pre
              style={{
                whiteSpace: "pre-wrap",
                maxHeight: 200,
                overflow: "auto",
                fontSize: 11,
                background: "#f8f8f8",
                padding: 8,
                borderRadius: 4,
              }}
            >
              {JSON.stringify(arr, null, 2)}
            </pre>
          )}
        </Panel>
      );
    }

    // Regular tabular feature set
    const data = features[k] as Record<string, number> | undefined;
    if (!data) return null;

    const tableData = featuresToTableData(data);

    return (
      <Panel
        key={k}
        header={
          <span>
            <BarChartOutlined /> {SECTION_INFO[k].title}
            <Tooltip title={SECTION_INFO[k].info}>
              <InfoCircleOutlined style={{ marginLeft: 8 }} />
            </Tooltip>
          </span>
        }
      >
        <Table
          size="small"
          columns={[
            { title: "Feature", dataIndex: "key", key: "key", width: "60%" },
            { title: "Value", dataIndex: "value", key: "value", width: "40%" },
          ]}
          dataSource={tableData}
          pagination={false}
          scroll={{ y: 250 }}
        />
      </Panel>
    );
  });

  return (
    <Modal
      open={open}
      onCancel={() => {
        setShowEmbedding(false);
        onClose();
      }}
      footer={null}
      title="Audio Features & Embeddings"
      width={1000}
      styles={{
        body: {
          maxHeight: "80vh",
          overflowY: "auto",
          padding: 24,
        },
      }}
    >
      <Collapse accordion>{panels.filter(Boolean)}</Collapse>
    </Modal>
  );
};

export default FeatureModal;
