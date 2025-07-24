import { useEffect, useState } from "react";
import {
  Card,
  Typography,
  Spin,
  List,
  Avatar,
  Button,
  Alert,
  Layout,
} from "antd";
import { InfoCircleOutlined, ArrowLeftOutlined } from "@ant-design/icons";
import { useParams, useNavigate } from "react-router-dom";

const { Title, Paragraph } = Typography;
const { Content } = Layout;

import FeatureModal from "../components/FeatureModal";
import MetricModal from "../components/MetricModal";

// ---- Type Definitions ----
interface TranscriptChunk {
  text: string;
  speaker: string | null;
  start: number | null;
  end: number | null;
  chunks: TranscriptChunk[] | null;
}

interface Transcript {
  text: string;
  speaker: string | null;
  start: number | null;
  end: number | null;
  chunks: TranscriptChunk[] | null;
}

interface Features {
  [key: string]: object;
}

interface Step {
  audio_file: string;
  features: Features;
  transcript: Transcript;
  speaker_embeddings: number[];
}

type MetricStats = {
  count?: number | null;
  sum?: number | null;
  avg?: number | null;
  std?: number | null;
  min?: number | null;
  max?: number | null;
};

function formatSessionId(id: string): { date: string; time: string; unique: string } {
  const [datePart, timePart, uniquePart] = id.split("_");
  if (!datePart || !timePart || !uniquePart) return { date: id, time: "", unique: "" };
  const date = `${datePart.slice(0, 4)}-${datePart.slice(4, 6)}-${datePart.slice(6, 8)}`;
  const time = `${timePart.slice(0, 2)}:${timePart.slice(2, 4)}:${timePart.slice(4, 6)}`;
  return { date, time, unique: uniquePart };
}

function formatTimestamp(file: string) {
  if (!file) return { date: "", time: "" };
  const fileName = file.split("/").pop() || file;
  const name = fileName.replace(/\.(wav|json)$/, "");
  const match = name.match(/^(\d{8})_(\d{6})/);
  if (!match) return { date: "", time: "" };
  const [, datePart, timePart] = match;
  const date = `${datePart.slice(0, 4)}-${datePart.slice(4, 6)}-${datePart.slice(6, 8)}`;
  const time = `${timePart.slice(0, 2)}:${timePart.slice(2, 4)}:${timePart.slice(4, 6)}`;
  return { date, time };
}

// ---- Main Component ----
export default function SessionDetail() {
  const { id } = useParams<{ id?: string }>();
  const navigate = useNavigate();

  const [steps, setSteps] = useState<Step[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const [modalFeatures, setModalFeatures] = useState<Features | null>(null);
  const [sessionMetrics, setSessionMetrics] = useState<Record<string, MetricStats | null>>({});
  const [metricsModalOpen, setMetricsModalOpen] = useState(false);

  useEffect(() => {
    setError(null);
    setSteps(null);

    fetch(`${import.meta.env.VITE_API_PROTOCOL}://${import.meta.env.VITE_API_HOST}:${import.meta.env.VITE_API_PORT}/api/session/${id}`)
      .then(async (res) => {
        const contentType = res.headers.get("content-type") || "";
        if (!res.ok || !contentType.includes("application/json")) {
          let errorMsg = `Unexpected response (${res.status})`;
          if (contentType.includes("application/json")) {
            try {
              const errJson = await res.json();
              errorMsg = errJson.error || errorMsg;
            } catch {
              // ignore
            }
          } else {
            const errText = await res.text();
            errorMsg = errText;
          }
          throw new Error(errorMsg);
        }
        return res.json();
      })
      .then((data) => {
        setSteps(data.data || []);
        setSessionMetrics(data.metrics_summary || {});
      })
      .catch((err) => {
        setError("Failed to load session data: " + err.message);
        setSteps([]);
      });
  }, [id]);

  if (error) {
    return (
      <Card style={{ maxWidth: 700, margin: "auto", marginTop: 60 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/sessions")} style={{ marginBottom: 16 }}>
          Back to Sessions
        </Button>
        <Alert type="error" message={error} showIcon />
      </Card>
    );
  }

  if (!steps) {
    return (
      <div style={{ display: "flex", justifyContent: "center", marginTop: 100 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Content style={{ padding: "32px 0", margin: "0 auto", width: "100%" }}>
        <div style={{ padding: "0 32px", marginBottom: 32, display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap" }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/sessions")} style={{ marginRight: 16 }}>
            Back to Sessions
          </Button>
          <Title level={4} style={{ margin: 0, flex: 1, textAlign: "center" }}>
            Session: {(() => {
              if (!id) return "";
              const { date, time, unique } = formatSessionId(id);
              return `${date} ${time} ${unique ? `(${unique})` : ""}`;
            })()}
            <InfoCircleOutlined
              onClick={() => setMetricsModalOpen(true)}
              style={{ fontSize: 20, marginLeft: 12, cursor: "pointer", verticalAlign: "middle" }}
            />
          </Title>
          <div style={{ width: 104 }} />
        </div>

        <div style={{ padding: "0 32px" }}>
          <List
            dataSource={steps}
            locale={{ emptyText: "No conversation steps found." }}
            renderItem={(step, idx) => {
              const isAgent = step.audio_file?.includes("AGENT");
              const avatarColor = isAgent ? "#52c41a" : "#1890ff";
              const displayName = isAgent ? "Agent" : "User";
              const features = step ? { ...step.features, embeddings: step.speaker_embeddings } : {};
              const text = step.transcript?.text || "(no transcript)";
              const audioSrc = `${import.meta.env.VITE_API_PROTOCOL}://${import.meta.env.VITE_API_HOST}:${import.meta.env.VITE_API_PORT}` + (step.audio_file || "");
              const { date, time } = formatTimestamp(step.audio_file || "");

              return (
                <List.Item
                  key={idx}
                  style={{
                    display: "grid",
                    gridTemplateColumns: isAgent ? "48px 1fr 32px" : "32px 1fr 48px",
                    justifyContent: "stretch",
                    alignItems: "flex-end",
                    marginBottom: 18,
                    background: "transparent",
                    border: "none",
                    boxShadow: "none",
                  }}
                >
                  {isAgent ? (
                    <Avatar style={{ backgroundColor: avatarColor, margin: "0 8px 0 0", gridRow: "1", gridColumn: "1", fontSize: 20 }} size={44}>
                      {displayName[0]}
                    </Avatar>
                  ) : (
                    <div style={{ width: 32 }} />
                  )}

                  <div
                    style={{
                      background: isAgent ? "#f6ffed" : "#99CCFF",
                      borderRadius: 18,
                      padding: "14px 20px",
                      margin: isAgent ? "0 0 0 12px" : "0 12px 0 0",
                      minWidth: 120,
                      width: "100%",
                      boxShadow: "0 2px 10px #e7e7e7",
                      position: "relative",
                      wordBreak: "break-word",
                    }}
                  >
                    <Paragraph style={{ marginBottom: 8, marginTop: 0 }}>
                      <b>{displayName}:</b> {text}
                    </Paragraph>
                    <Paragraph style={{ marginBottom: 8, marginTop: 0, fontSize: "0.85em", color: "#888" }}>
                      {date && time ? `${date} ${time}` : ""}
                    </Paragraph>
                    <audio src={audioSrc} controls style={{ marginTop: 6, width: "100%" }} />
                    <Button
                      type="text"
                      icon={<InfoCircleOutlined style={{ fontSize: 20 }} />}
                      onClick={() => {
                        setModalFeatures(features);
                        setModalOpen(true);
                      }}
                      style={{ position: "absolute", bottom: 8, right: isAgent ? 8 : undefined, left: !isAgent ? 8 : undefined }}
                    />
                  </div>

                  {!isAgent ? (
                    <Avatar style={{ backgroundColor: avatarColor, margin: "0 0 0 8px", gridRow: "1", gridColumn: "3", fontSize: 20 }} size={44}>
                      {displayName[0]}
                    </Avatar>
                  ) : (
                    <div style={{ width: 32 }} />
                  )}
                </List.Item>
              );
            }}
          />
        </div>

        <FeatureModal open={modalOpen} onClose={() => setModalOpen(false)} features={modalFeatures} />
        <MetricModal
          open={metricsModalOpen}
          onClose={() => setMetricsModalOpen(false)}
          metrics={{
            processors: {
              summary: Object.fromEntries(
                Object.entries(sessionMetrics)
                  .filter(([, v]) => v !== null)
                  .map(([k, v]) => [k, v as MetricStats]) // Cast because we've filtered out null
              ),
            },
          }}
        />
      </Content>
    </Layout>
  );
}
