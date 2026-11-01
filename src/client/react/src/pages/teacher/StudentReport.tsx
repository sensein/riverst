/**
 * StudentReport.tsx
 * /teacher/students/:id/report — a printable progress report for conferences or records.
 */

import React, { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Descriptions,
  Divider,
  Result,
  Space,
  Spin,
  Table,
  Typography,
} from "antd";
import { ArrowLeftOutlined, PrinterOutlined } from "@ant-design/icons";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import {
  COMPLETION_LABELS,
  LOAD_ERROR,
  WORD_STATUS_LABELS,
  formatDate,
  gradeBandLabel,
} from "../../components/teacher/labels";
import type { Note, StudentDetailData } from "../../components/teacher/types";
import { httpStatus } from "../../utils/studentCode";

type ReportData = StudentDetailData & { notes: Note[]; generated_at: string };

const PRINT_CSS = `
@media print {
  .no-print { display: none !important; }
  body { background: #fff !important; }
  .report-page { padding: 0 !important; max-width: none !important; }
}
`;

const StudentReport: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { authRequest } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState<ReportData | null>(null);
  const [error, setError] = useState<"not_found" | "failed" | null>(null);

  useEffect(() => {
    authRequest
      .get(`/api/teacher/students/${id}/report`)
      .then((res) => setData(res.data))
      .catch((err) =>
        setError(httpStatus(err) === 404 ? "not_found" : "failed"),
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (error === "not_found")
    return <Result status="404" title="Student not found" />;
  if (error)
    return (
      <Alert
        type="error"
        showIcon
        message={LOAD_ERROR}
        style={{ margin: 16 }}
      />
    );
  if (!data) {
    return (
      <div style={{ textAlign: "center", padding: 48 }}>
        <Spin size="large" />
      </div>
    );
  }

  const { student, counts } = data;
  const groups: [string, string][] = [
    ["still_learning", WORD_STATUS_LABELS.still_learning],
    ["mastered", WORD_STATUS_LABELS.mastered],
    ["already_knew", WORD_STATUS_LABELS.already_knew],
  ];

  return (
    <div
      className="report-page"
      style={{
        maxWidth: 800,
        margin: "0 auto",
        padding: 16,
        background: "#fff",
        minHeight: "100vh",
      }}
    >
      <style>{PRINT_CSS}</style>
      <Space className="no-print" style={{ marginBottom: 16 }}>
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate(`/teacher/students/${id}`)}
        >
          Back
        </Button>
        <Button
          type="primary"
          icon={<PrinterOutlined />}
          onClick={() => window.print()}
        >
          Print
        </Button>
      </Space>

      <Typography.Title level={2}>
        {student.display_name}: vocabulary progress
      </Typography.Title>
      <Typography.Text type="secondary">
        Prepared {formatDate(data.generated_at)} · KIVA vocabulary practice
      </Typography.Text>

      <Descriptions bordered size="small" column={2} style={{ marginTop: 16 }}>
        <Descriptions.Item label="Reading level">
          {student.reading_level.label}
          {student.reading_level.source === "teacher"
            ? " (set by teacher)"
            : ""}
        </Descriptions.Item>
        <Descriptions.Item label="Sessions">
          {data.sessions.length}
        </Descriptions.Item>
        <Descriptions.Item label="Words taught">
          {counts.taught}
        </Descriptions.Item>
        <Descriptions.Item label="Mastered">
          {counts.mastered}
        </Descriptions.Item>
        <Descriptions.Item label="Still learning">
          {counts.still_learning}
        </Descriptions.Item>
        <Descriptions.Item label="Already knew">
          {counts.already_knew}
        </Descriptions.Item>
      </Descriptions>

      {data.summary.status === "ready" && data.summary.text && (
        <>
          <Divider orientation="left">Summary</Divider>
          <Typography.Paragraph>{data.summary.text}</Typography.Paragraph>
        </>
      )}

      <Divider orientation="left">Words</Divider>
      {groups.map(([status, label]) => {
        const list = data.words.filter((w) => w.status === status);
        return (
          <Typography.Paragraph key={status}>
            <Typography.Text strong>
              {label} ({list.length}):{" "}
            </Typography.Text>
            {list.length
              ? list
                  .map((w) => `${w.word} (${gradeBandLabel(w.grade_band)})`)
                  .join(", ")
              : "none"}
          </Typography.Paragraph>
        );
      })}

      <Divider orientation="left">Sessions</Divider>
      <Table
        size="small"
        rowKey="id"
        pagination={false}
        dataSource={data.sessions}
        locale={{ emptyText: "No sessions yet." }}
        columns={[
          {
            title: "Date",
            dataIndex: "started_at",
            render: (iso: string) => formatDate(iso),
          },
          {
            title: "Book",
            dataIndex: "book_title",
            render: (t: string | null, s) =>
              [t, s.chapter ? `Ch. ${s.chapter}` : null]
                .filter(Boolean)
                .join(" · "),
          },
          {
            title: "Mastered",
            render: (_, s) =>
              s.detail === "ready"
                ? `${s.words_mastered} of ${s.words_taught}`
                : "—",
          },
          {
            title: "Status",
            dataIndex: "completion",
            render: (c: string | null) => (c ? COMPLETION_LABELS[c] : "—"),
          },
        ]}
      />

      {data.notes.length > 0 && (
        <>
          <Divider orientation="left">Teacher notes</Divider>
          {data.notes.map((n) => (
            <Typography.Paragraph key={n.id}>
              <Typography.Text type="secondary">
                {formatDate(n.created_at)}:{" "}
              </Typography.Text>
              <span style={{ whiteSpace: "pre-wrap" }}>{n.body}</span>
            </Typography.Paragraph>
          ))}
        </>
      )}
    </div>
  );
};

export default StudentReport;
