/**
 * SessionDetail.tsx
 * /teacher/sessions/:id — one session: summary, words the student already knew, and each taught word's
 * four teaching steps with the review result. Shows outcomes only, never the student's own words.
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Alert,
  App,
  Breadcrumb,
  Button,
  Card,
  Collapse,
  Descriptions,
  Empty,
  List,
  Result,
  Space,
  Spin,
  Tag,
  Typography,
} from "antd";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import TeacherLayout from "../../components/teacher/TeacherLayout";
import StepOutcome from "../../components/teacher/StepOutcome";
import NotesPanel from "../../components/teacher/NotesPanel";
import {
  COMPLETION_LABELS,
  ENGAGEMENT_LABELS,
  LOAD_ERROR,
  REVIEW_LABELS,
  STEP_ORDER,
  formatDate,
  formatDuration,
  gradeBandLabel,
} from "../../components/teacher/labels";
import type { SessionDetailData } from "../../components/teacher/types";
import { httpStatus } from "../../utils/studentCode";

const POLL_MS = 15_000;
const MAX_POLLS = 8;
const REVIEW_COLORS: Record<string, string> = {
  mastered: "green",
  not_mastered: "orange",
  not_reached: "default",
};
const ENGAGEMENT_COLORS: Record<string, string> = {
  high: "green",
  mixed: "gold",
  low: "orange",
};

const SessionDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { authRequest } = useAuth();
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [data, setData] = useState<SessionDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<"not_found" | "failed" | null>(null);
  const [retrying, setRetrying] = useState(false);
  const polls = useRef(0);

  const load = useCallback(async () => {
    try {
      const res = await authRequest.get(`/api/teacher/sessions/${id}`);
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
    polls.current = 0;
    setLoading(true);
    load();
  }, [load]);

  const waiting =
    data && (data.detail === "pending" || data.summary.status === "pending");
  useEffect(() => {
    if (!waiting || polls.current >= MAX_POLLS) return;
    const timer = setTimeout(() => {
      polls.current += 1;
      load();
    }, POLL_MS);
    return () => clearTimeout(timer);
  }, [waiting, data, load]);

  const retry = async () => {
    setRetrying(true);
    try {
      await authRequest.post(`/api/teacher/sessions/${id}/retry`, {});
      message.info("Working on it…");
      polls.current = 0;
      await load();
    } catch (err) {
      message.error(
        httpStatus(err) === 409
          ? "Already working on it."
          : "We couldn't retry right now. Try again later.",
      );
    } finally {
      setRetrying(false);
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
          title="Session not found"
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

  const { session, summary } = data;
  const retryButton = (
    <Button size="small" onClick={retry} loading={retrying}>
      Retry
    </Button>
  );

  const summaryCard = (
    <Card title="How the session went">
      {summary.status === "ready" ? (
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          {summary.engagement && (
            <Tag color={ENGAGEMENT_COLORS[summary.engagement]}>
              {ENGAGEMENT_LABELS[summary.engagement]}
            </Tag>
          )}
          <Typography.Paragraph style={{ marginBottom: 0 }}>
            {summary.text}
          </Typography.Paragraph>
          {!!summary.words_went_well?.length && (
            <Space wrap>
              <Typography.Text strong>Went well:</Typography.Text>
              {summary.words_went_well.map((w) => (
                <Tag key={w} color="green">
                  {w}
                </Tag>
              ))}
            </Space>
          )}
          {!!summary.words_hard?.length && (
            <Space wrap>
              <Typography.Text strong>Was hard:</Typography.Text>
              {summary.words_hard.map((w) => (
                <Tag key={w} color="orange">
                  {w}
                </Tag>
              ))}
            </Space>
          )}
          {!!summary.notable_moments?.length && (
            <div>
              <Typography.Text strong>Notable</Typography.Text>
              <List
                size="small"
                dataSource={summary.notable_moments}
                renderItem={(m) => <List.Item>{m}</List.Item>}
              />
            </div>
          )}
          {!!summary.suggestions?.length && (
            <div>
              <Typography.Text strong>Suggestions</Typography.Text>
              <List
                size="small"
                dataSource={summary.suggestions}
                renderItem={(m) => <List.Item>{m}</List.Item>}
              />
            </div>
          )}
        </Space>
      ) : summary.status === "pending" ? (
        <Space>
          <Spin size="small" />
          <Typography.Text type="secondary">
            The summary is being prepared. Check back in a minute.
          </Typography.Text>
        </Space>
      ) : (
        <Alert
          type="info"
          showIcon
          message="Summary unavailable"
          action={data.detail !== "not_applicable" ? retryButton : undefined}
        />
      )}
    </Card>
  );

  return (
    <TeacherLayout>
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Breadcrumb
          items={[
            { title: <Link to="/teacher">My class</Link> },
            {
              title: (
                <Link to={`/teacher/students/${session.student_id}`}>
                  {session.student_name}
                </Link>
              ),
            },
            { title: formatDate(session.started_at) },
          ]}
        />
        <Typography.Title level={2} style={{ margin: 0 }}>
          {session.student_name}'s session
        </Typography.Title>

        <Card>
          <Descriptions column={{ xs: 1, sm: 2, md: 3 }} size="small">
            <Descriptions.Item label="Date">
              {formatDate(session.started_at)}
            </Descriptions.Item>
            <Descriptions.Item label="Book">
              {session.book_title ?? "—"}
            </Descriptions.Item>
            <Descriptions.Item label="Chapter">
              {session.chapter ?? "—"}
            </Descriptions.Item>
            <Descriptions.Item label="Length">
              {formatDuration(session.duration_seconds) || "—"}
            </Descriptions.Item>
            <Descriptions.Item label="Status">
              {session.completion ? (
                <Tag
                  color={
                    session.completion === "completed" ? "green" : "default"
                  }
                >
                  {COMPLETION_LABELS[session.completion]}
                </Tag>
              ) : (
                "In progress"
              )}
            </Descriptions.Item>
            {session.teacher_selected_words && (
              <Descriptions.Item label="Words">
                Chosen by teacher
              </Descriptions.Item>
            )}
          </Descriptions>
        </Card>

        {data.detail === "not_applicable" ? (
          <Card>
            <Empty
              description={`${session.activity_label} doesn't have vocabulary results.`}
            />
          </Card>
        ) : (
          <>
            {summaryCard}

            {data.detail === "pending" && (
              <Alert
                type="info"
                showIcon
                message="Results are being prepared. Check back in a minute."
              />
            )}
            {data.detail === "unavailable" && (
              <Alert
                type="warning"
                showIcon
                message="Detailed results not available for this session."
                action={retryButton}
              />
            )}

            <Card title="Already knew it">
              {data.already_knew.length ? (
                <Space wrap>
                  {data.already_knew.map((w) => (
                    <Tag key={w.word} color="blue">
                      {w.word} · {gradeBandLabel(w.grade_band)}
                    </Tag>
                  ))}
                </Space>
              ) : (
                <Typography.Text type="secondary">
                  No words were skipped as already known.
                </Typography.Text>
              )}
            </Card>

            <Card title="Words taught">
              {data.taught.length ? (
                <Collapse
                  defaultActiveKey={data.taught.map((w) => w.word)}
                  items={data.taught.map((w) => ({
                    key: w.word,
                    label: (
                      <Space wrap>
                        <Typography.Text strong>{w.word}</Typography.Text>
                        <Typography.Text type="secondary">
                          {gradeBandLabel(w.grade_band)}
                        </Typography.Text>
                        {w.teacher_selected && <Tag>Chosen by teacher</Tag>}
                      </Space>
                    ),
                    extra: w.review ? (
                      <Tag color={REVIEW_COLORS[w.review]}>
                        {REVIEW_LABELS[w.review]}
                      </Tag>
                    ) : null,
                    children: (
                      <Space
                        direction="vertical"
                        size={8}
                        style={{ width: "100%" }}
                      >
                        {STEP_ORDER.map((step) => (
                          <StepOutcome
                            key={step}
                            step={step}
                            result={w.steps[step]}
                          />
                        ))}
                      </Space>
                    ),
                  }))}
                />
              ) : (
                <Typography.Text type="secondary">
                  No new words were taught in this session.
                </Typography.Text>
              )}
            </Card>
          </>
        )}

        <NotesPanel targetType="session" targetId={session.id} />
      </Space>
    </TeacherLayout>
  );
};

export default SessionDetail;
