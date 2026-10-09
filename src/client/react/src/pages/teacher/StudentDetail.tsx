/**
 * StudentDetail.tsx
 * /teacher/students/:id — one student's reading level, vocabulary progress, words, sessions and summary.
 */

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  App,
  Breadcrumb,
  Button,
  Card,
  Col,
  Dropdown,
  Input,
  List,
  Modal,
  Result,
  Row,
  Segmented,
  Select,
  Space,
  Spin,
  Statistic,
  Table,
  Tag,
  Typography,
} from "antd";
import { MoreOutlined, PrinterOutlined } from "@ant-design/icons";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import TeacherLayout from "../../components/teacher/TeacherLayout";
import StatusTag from "../../components/teacher/StatusTag";
import ReadingLevel from "../../components/teacher/ReadingLevel";
import LevelTrend from "../../components/teacher/LevelTrend";
import NotesPanel from "../../components/teacher/NotesPanel";
import StudentCode from "../../components/teacher/StudentCode";
import { httpStatus } from "../../utils/studentCode";
import {
  COMPLETION_LABELS,
  LOAD_ERROR,
  WORD_STATUS_LABELS,
  formatDate,
  gradeBandLabel,
} from "../../components/teacher/labels";
import type {
  SessionListItem,
  StudentDetailData,
  StudentWord,
} from "../../components/teacher/types";

type WordFilter = "all" | "still_learning" | "mastered" | "already_knew";

const WORD_COLORS: Record<string, string> = {
  mastered: "green",
  still_learning: "orange",
  already_knew: "blue",
};

const LEVEL_OPTIONS = [
  { label: "Use estimate", value: "estimate" },
  ...[3, 4, 5, 6, 7, 8].map((g) => ({ label: `Grade ${g}`, value: String(g) })),
];

const sessionLine = (s: SessionListItem): React.ReactNode => {
  if (s.detail === "pending")
    return (
      <Typography.Text type="secondary">
        Results are being prepared…
      </Typography.Text>
    );
  if (s.detail === "unavailable")
    return (
      <Typography.Text type="secondary">
        Detailed results not available
      </Typography.Text>
    );
  if (s.detail === "not_applicable")
    return (
      <Typography.Text type="secondary">No vocabulary results</Typography.Text>
    );
  if (s.words_taught === 0)
    return (
      <Typography.Text type="secondary">No new words taught</Typography.Text>
    );
  return `${s.words_mastered} of ${s.words_taught} new words mastered`;
};

const StudentDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { authRequest } = useAuth();
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [data, setData] = useState<StudentDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<"not_found" | "failed" | null>(null);
  const [wordFilter, setWordFilter] = useState<WordFilter>("all");
  const [renaming, setRenaming] = useState(false);
  const [newName, setNewName] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await authRequest.get(`/api/teacher/students/${id}`);
      setData(res.data);
      setError(null);
    } catch (err) {
      setError(httpStatus(err) === 404 ? "not_found" : "failed");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const words = useMemo(
    () =>
      data
        ? data.words.filter(
            (w) => wordFilter === "all" || w.status === wordFilter,
          )
        : [],
    [data, wordFilter],
  );

  const patch = async (changes: Record<string, unknown>, done: string) => {
    try {
      await authRequest.patch(`/api/teacher/students/${id}`, changes);
      message.success(done);
      await load();
    } catch {
      message.error("We couldn't save that change. Try again.");
    }
  };

  const regenerate = async () => {
    try {
      await authRequest.post(`/api/teacher/students/${id}/code`, {});
      message.success("New code created. The old code no longer works.");
      await load();
    } catch {
      message.error("We couldn't create a new code. Try again.");
    }
  };

  if (loading && !data) {
    return (
      <TeacherLayout>
        <div style={{ textAlign: "center", padding: 48 }}>
          <Spin size="large" />
        </div>
      </TeacherLayout>
    );
  }

  if (error === "not_found") {
    return (
      <TeacherLayout>
        <Result
          status="404"
          title="Student not found"
          extra={
            <Button onClick={() => navigate("/teacher")}>
              Back to my class
            </Button>
          }
        />
      </TeacherLayout>
    );
  }

  if (error || !data) {
    return (
      <TeacherLayout>
        <Alert
          type="error"
          showIcon
          message={LOAD_ERROR}
          action={<Button onClick={load}>Try again</Button>}
        />
      </TeacherLayout>
    );
  }

  const { student, counts, summary } = data;
  const archived = student.status === "archived";

  return (
    <TeacherLayout>
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Breadcrumb
          items={[
            { title: <Link to="/teacher">My class</Link> },
            { title: student.display_name },
          ]}
        />

        <Space style={{ width: "100%", justifyContent: "space-between" }} wrap>
          <Space size={12} wrap>
            <Typography.Title level={2} style={{ margin: 0 }}>
              {student.display_name}
            </Typography.Title>
            <StatusTag status={student.class_status} />
          </Space>
          <Space wrap>
            <Button
              icon={<PrinterOutlined />}
              onClick={() => navigate(`/teacher/students/${id}/report`)}
            >
              Print report
            </Button>
            <Dropdown
              trigger={["click"]}
              menu={{
                items: [
                  { key: "rename", label: "Rename" },
                  { key: "code", label: "Make a new code" },
                  {
                    key: "archive",
                    label: archived ? "Restore to class" : "Archive",
                  },
                ],
                onClick: ({ key }) => {
                  if (key === "rename") {
                    setNewName(student.display_name);
                    setRenaming(true);
                  } else if (key === "code") {
                    Modal.confirm({
                      title: "Make a new code?",
                      content: `${student.display_name}'s current code and link will stop working. Past sessions stay linked.`,
                      okText: "Make new code",
                      onOk: regenerate,
                    });
                  } else if (key === "archive") {
                    patch(
                      { status: archived ? "active" : "archived" },
                      archived
                        ? "Student restored."
                        : "Student archived. Their history is kept.",
                    );
                  }
                },
              }}
            >
              <Button icon={<MoreOutlined />}>More</Button>
            </Dropdown>
          </Space>
        </Space>

        <Row gutter={[16, 16]}>
          <Col xs={24} md={12}>
            <Card title="Reading level" style={{ height: "100%" }}>
              <Space direction="vertical" size={16} style={{ width: "100%" }}>
                <Typography.Title level={3} style={{ margin: 0 }}>
                  <ReadingLevel
                    level={student.reading_level}
                    estimate={student.reading_level_estimate}
                  />
                </Typography.Title>
                <LevelTrend trend={data.reading_level_trend} />
                <Space wrap>
                  <Typography.Text>Set level:</Typography.Text>
                  <Select
                    style={{ minWidth: 160 }}
                    value={
                      student.reading_level_override
                        ? String(student.reading_level_override)
                        : "estimate"
                    }
                    options={LEVEL_OPTIONS}
                    onChange={(value) =>
                      patch(
                        {
                          reading_level_override:
                            value === "estimate" ? null : Number(value),
                        },
                        value === "estimate"
                          ? "Using the automatic estimate."
                          : "Reading level set.",
                      )
                    }
                  />
                </Space>
                <Typography.Text type="secondary">
                  Estimated from the grade level of words {student.display_name}{" "}
                  masters or already knows.
                </Typography.Text>
              </Space>
            </Card>
          </Col>
          <Col xs={24} md={12}>
            <Card title="Student code" style={{ height: "100%" }}>
              <Typography.Paragraph type="secondary">
                {student.display_name} enters this code when starting KIVA, or
                opens the link.
              </Typography.Paragraph>
              <StudentCode code={student.code} link={student.link} />
            </Card>
          </Col>
        </Row>

        <Row gutter={[16, 16]}>
          {[
            ["Already knew it", counts.already_knew],
            ["Words taught", counts.taught],
            ["Mastered", counts.mastered],
            ["Still learning", counts.still_learning],
          ].map(([title, value]) => (
            <Col xs={12} md={6} key={title as string}>
              <Card>
                <Statistic title={title} value={value as number} />
              </Card>
            </Col>
          ))}
        </Row>

        <Card title="Summary">
          {summary.status === "ready" && summary.text ? (
            <Typography.Paragraph style={{ marginBottom: 0 }}>
              {summary.text}
            </Typography.Paragraph>
          ) : summary.status === "failed" ? (
            <Typography.Text type="secondary">
              The summary isn't available right now. It will try again after the
              next session.
            </Typography.Text>
          ) : (
            <Typography.Text type="secondary">
              A summary will appear after {student.display_name}'s next session.
            </Typography.Text>
          )}
        </Card>

        <Card
          title="Words"
          extra={
            <Segmented
              size="small"
              value={wordFilter}
              onChange={(v) => setWordFilter(v as WordFilter)}
              options={[
                { label: "All", value: "all" },
                { label: "Still learning", value: "still_learning" },
                { label: "Mastered", value: "mastered" },
                { label: "Already knew it", value: "already_knew" },
              ]}
            />
          }
        >
          <Table<StudentWord>
            rowKey="word"
            size="small"
            dataSource={words}
            pagination={words.length > 20 ? { pageSize: 20 } : false}
            locale={{
              emptyText: data.words.length
                ? "No words match this filter."
                : "No words yet.",
            }}
            columns={[
              {
                title: "Word",
                dataIndex: "word",
                sorter: (a, b) => a.word.localeCompare(b.word),
              },
              {
                title: "Status",
                dataIndex: "status",
                render: (status: string) => (
                  <Tag color={WORD_COLORS[status]}>
                    {WORD_STATUS_LABELS[status]}
                  </Tag>
                ),
              },
              {
                title: "Level",
                dataIndex: "grade_band",
                render: (band: number | null) => gradeBandLabel(band),
              },
              {
                title: "Last seen",
                dataIndex: "last_seen_at",
                render: (iso: string, w) => (
                  <Link to={`/teacher/sessions/${w.last_seen_session_id}`}>
                    {formatDate(iso)}
                  </Link>
                ),
              },
            ]}
          />
        </Card>

        <Card title="Sessions">
          <List
            dataSource={data.sessions}
            locale={{
              emptyText: `No sessions yet. Share ${student.display_name}'s code to get started.`,
            }}
            renderItem={(s) => (
              <List.Item
                actions={[
                  <Link key="open" to={`/teacher/sessions/${s.id}`}>
                    Open
                  </Link>,
                ]}
              >
                <List.Item.Meta
                  title={
                    <Space wrap>
                      <Link to={`/teacher/sessions/${s.id}`}>
                        {formatDate(s.started_at)}
                      </Link>
                      {s.completion === "ended_early" && (
                        <Tag>{COMPLETION_LABELS.ended_early}</Tag>
                      )}
                    </Space>
                  }
                  description={
                    <Space direction="vertical" size={0}>
                      <span>
                        {[
                          s.book_title,
                          s.chapter ? `Chapter ${s.chapter}` : null,
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </span>
                      <span>{sessionLine(s)}</span>
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        </Card>

        <NotesPanel targetType="student" targetId={student.id} />
      </Space>

      <Modal
        open={renaming}
        title="Rename student"
        okText="Save"
        onCancel={() => setRenaming(false)}
        okButtonProps={{ disabled: !newName.trim() }}
        onOk={async () => {
          await patch({ display_name: newName.trim() }, "Name updated.");
          setRenaming(false);
        }}
      >
        <Input
          value={newName}
          maxLength={40}
          onChange={(e) => setNewName(e.target.value)}
          autoFocus
        />
      </Modal>
    </TeacherLayout>
  );
};

export default StudentDetail;
