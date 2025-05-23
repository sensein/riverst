import React from "react";
import { Modal, Collapse, Tooltip, Table, Button } from "antd";
import { InfoCircleOutlined, BarChartOutlined, CodeOutlined } from "@ant-design/icons";

// Helpers for describing sections
const SECTION_INFO = {
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

// Utility for formatting numeric values
const pretty = (v) =>
  typeof v === "number" ? v.toFixed(4) : (v == null ? "–" : String(v));

// For feature tables
function featuresToTableData(obj) {
  return Object.entries(obj).map(([key, value]) => ({
    key,
    value: pretty(value),
  }));
}

function FeatureModal({ open, onClose, features }) {
  const [showEmbedding, setShowEmbedding] = React.useState(false);

  // Null guard
  if (!features) {
    return (
      <Modal open={open} onCancel={onClose} footer={null} title="Audio Features" destroyOnHidden>
        <p>No feature data available.</p>
      </Modal>
    );
  }

  // Compose collapsible panels
  const panels = Object.keys(SECTION_INFO).map((k) => {
    if (!(k in features)) return null;
    if (k === "embeddings") {
      const arr = features.embeddings || [];
      return (
        <Collapse.Panel
          key={k}
          header={
            <span>
              <BarChartOutlined /> {SECTION_INFO[k].title}{" "}
              <Tooltip title={SECTION_INFO[k].info}>
                <InfoCircleOutlined style={{ marginLeft: 8 }} />
              </Tooltip>
            </span>
          }
        >
          <div style={{ marginBottom: 8 }}>
            <b>Length:</b> {arr.length}
            {"  |  "}
            <b>Mean:</b> {arr.length ? pretty(arr.reduce((a, b) => a + b, 0) / arr.length) : "–"}
            {"  |  "}
            <b>Std:</b>{" "}
            {arr.length
              ? pretty(
                  Math.sqrt(
                    arr.reduce((a, b) => a + Math.pow(b - arr.reduce((a, b) => a + b, 0) / arr.length, 2), 0) /
                      arr.length
                  )
                )
              : "–"}
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
            <pre style={{ whiteSpace: "pre-wrap", maxHeight: 200, overflow: "auto", fontSize: 11, background: "#f8f8f8", padding: 8, borderRadius: 4 }}>
              {JSON.stringify(arr, null, 2)}
            </pre>
          )}
        </Collapse.Panel>
      );
    }

    const tableData = featuresToTableData(features[k]);
    return (
      <Collapse.Panel
        key={k}
        header={
          <span>
            <BarChartOutlined /> {SECTION_INFO[k].title}{" "}
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
      </Collapse.Panel>
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
        <Collapse accordion>
            {panels.filter(Boolean)}
        </Collapse>
    </Modal>

  );
}

export default FeatureModal;
