/**
 * WordInsights.tsx
 * /teacher/words — which words are hardest across the class, and who is still learning each one.
 */

import React, { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Empty,
  Grid,
  Progress,
  Space,
  Spin,
  Table,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { Link } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import TeacherLayout from "../../components/teacher/TeacherLayout";
import {
  LOAD_ERROR,
  STEP_LABELS,
  gradeBandLabel,
} from "../../components/teacher/labels";
import type { WordInsight } from "../../components/teacher/types";

const WordInsights: React.FC = () => {
  const { authRequest } = useAuth();
  const screens = Grid.useBreakpoint();
  const [words, setWords] = useState<WordInsight[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await authRequest.get("/api/teacher/insights/words", {
        params: { sort: "mastery_rate" },
      });
      setWords(res.data.words);
      setFailed(false);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const columns: ColumnsType<WordInsight> = [
    {
      title: "Word",
      dataIndex: "word",
      sorter: (a, b) => a.word.localeCompare(b.word),
    },
    ...(screens.md
      ? [
          {
            title: "Level",
            dataIndex: "grade_band",
            render: (b: number | null) => gradeBandLabel(b),
          },
          {
            title: "Already knew",
            dataIndex: "already_knew",
            align: "right" as const,
          },
        ]
      : []),
    {
      title: "Taught",
      dataIndex: "taught",
      align: "right",
      sorter: (a, b) => a.taught - b.taught,
    },
    {
      title: "Still learning",
      dataIndex: "still_learning",
      align: "right",
      sorter: (a, b) => a.still_learning - b.still_learning,
    },
    {
      title: "Mastered",
      dataIndex: "mastery_rate",
      sorter: (a, b) => (a.mastery_rate ?? 2) - (b.mastery_rate ?? 2),
      render: (rate: number | null, w) =>
        rate == null ? (
          <Typography.Text type="secondary">Not taught</Typography.Text>
        ) : (
          <Space size={8}>
            <Progress
              percent={Math.round(rate * 100)}
              size="small"
              style={{ width: 80, margin: 0 }}
              showInfo={false}
            />
            <span>
              {w.mastered}/{w.taught}
            </span>
          </Space>
        ),
    },
    ...(screens.md
      ? [
          {
            title: "Hardest step",
            dataIndex: "hardest_step",
            render: (step: string | null) => (step ? STEP_LABELS[step] : "—"),
          },
        ]
      : []),
  ];

  return (
    <TeacherLayout>
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Typography.Title level={2} style={{ margin: 0 }}>
          Words across my class
        </Typography.Title>
        <Typography.Text type="secondary">
          Hardest words first. Open a row to see who is still learning it.
        </Typography.Text>
        {failed ? (
          <Alert
            type="error"
            showIcon
            message={LOAD_ERROR}
            action={<Button onClick={load}>Try again</Button>}
          />
        ) : loading && !words.length ? (
          <div style={{ textAlign: "center", padding: 48 }}>
            <Spin size="large" />
          </div>
        ) : !words.length ? (
          <Card>
            <Empty description="Word insights appear after your students complete sessions." />
          </Card>
        ) : (
          <Table
            rowKey="word"
            columns={columns}
            dataSource={words}
            loading={loading}
            pagination={words.length > 50 ? { pageSize: 50 } : false}
            scroll={{ x: true }}
            expandable={{
              rowExpandable: (w) => w.still_learning_students.length > 0,
              expandedRowRender: (w) => (
                <Space wrap>
                  <Typography.Text>Still learning:</Typography.Text>
                  {w.still_learning_students.map((s) => (
                    <Link key={s.id} to={`/teacher/students/${s.id}`}>
                      {s.display_name}
                    </Link>
                  ))}
                </Space>
              ),
            }}
          />
        )}
      </Space>
    </TeacherLayout>
  );
};

export default WordInsights;
