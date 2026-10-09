/**
 * ClassOverview.tsx
 * /teacher — the class at a glance: status, last session, reading level and words mastered for every student.
 */

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Empty,
  Grid,
  Segmented,
  Space,
  Spin,
  Switch,
  Table,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { PlusOutlined } from "@ant-design/icons";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import TeacherLayout from "../../components/teacher/TeacherLayout";
import AddStudentModal from "../../components/teacher/AddStudentModal";
import StatusTag from "../../components/teacher/StatusTag";
import ReadingLevel from "../../components/teacher/ReadingLevel";
import { LOAD_ERROR, formatRelative } from "../../components/teacher/labels";
import type { ClassStudent } from "../../components/teacher/types";

type StatusFilter = "all" | "needs_attention" | "inactive" | "on_track";

const ClassOverview: React.FC = () => {
  const { authRequest } = useAuth();
  const navigate = useNavigate();
  const screens = Grid.useBreakpoint();
  const [students, setStudents] = useState<ClassStudent[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [showArchived, setShowArchived] = useState(false);
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await authRequest.get("/api/teacher/class", {
        params: { status: showArchived ? "archived" : "active" },
      });
      setStudents(res.data.students);
      setFailed(false);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showArchived]);

  useEffect(() => {
    load();
  }, [load]);

  const visible = useMemo(
    () =>
      filter === "all" ? students : students.filter((s) => s.status === filter),
    [students, filter],
  );
  const needAttention = students.filter(
    (s) => s.status === "needs_attention",
  ).length;

  const columns: ColumnsType<ClassStudent> = [
    {
      title: "Name",
      dataIndex: "display_name",
      sorter: (a, b) => a.display_name.localeCompare(b.display_name),
      render: (name: string, s) => (
        <Link to={`/teacher/students/${s.id}`}>{name}</Link>
      ),
    },
    {
      title: "Status",
      dataIndex: "status",
      render: (status: string) => <StatusTag status={status} />,
    },
    {
      title: "Last session",
      dataIndex: "last_session_at",
      sorter: (a, b) =>
        (a.last_session_at ?? "").localeCompare(b.last_session_at ?? ""),
      render: (iso: string | null) =>
        iso ? (
          formatRelative(iso)
        ) : (
          <Typography.Text type="secondary">No sessions yet</Typography.Text>
        ),
    },
    ...(screens.md
      ? [
          {
            title: "Sessions",
            dataIndex: "sessions_completed",
            align: "right" as const,
          },
          {
            title: "Reading level",
            dataIndex: "reading_level",
            render: (level: ClassStudent["reading_level"]) => (
              <ReadingLevel level={level} />
            ),
          },
        ]
      : []),
    {
      title: "Words mastered",
      dataIndex: "words_mastered",
      align: "right",
      sorter: (a, b) => a.words_mastered - b.words_mastered,
    },
  ];

  return (
    <TeacherLayout>
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Space style={{ width: "100%", justifyContent: "space-between" }} wrap>
          <Typography.Title level={2} style={{ margin: 0 }}>
            My class
          </Typography.Title>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setAdding(true)}
          >
            Add student
          </Button>
        </Space>

        {!showArchived && needAttention > 0 && (
          <Alert
            type="warning"
            showIcon
            message={`${needAttention} student${needAttention === 1 ? "" : "s"} may need attention`}
            description="In each of their last two sessions, half or more of the new words weren't mastered yet."
            action={
              <Button size="small" onClick={() => setFilter("needs_attention")}>
                Show
              </Button>
            }
          />
        )}

        <Space style={{ width: "100%", justifyContent: "space-between" }} wrap>
          <Segmented
            value={filter}
            onChange={(v) => setFilter(v as StatusFilter)}
            disabled={showArchived}
            options={[
              { label: "All", value: "all" },
              { label: "Needs attention", value: "needs_attention" },
              { label: "Inactive", value: "inactive" },
              { label: "On track", value: "on_track" },
            ]}
          />
          <Space>
            <Typography.Text>Show archived</Typography.Text>
            <Switch
              checked={showArchived}
              onChange={(checked) => {
                setShowArchived(checked);
                setFilter("all");
              }}
            />
          </Space>
        </Space>

        {failed ? (
          <Alert
            type="error"
            showIcon
            message={LOAD_ERROR}
            action={<Button onClick={load}>Try again</Button>}
          />
        ) : loading && students.length === 0 ? (
          <div style={{ textAlign: "center", padding: 48 }}>
            <Spin size="large" />
          </div>
        ) : students.length === 0 ? (
          <Card>
            <Empty
              description={
                showArchived
                  ? "No archived students."
                  : "Add your first student to get started."
              }
            >
              {!showArchived && (
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => setAdding(true)}
                >
                  Add student
                </Button>
              )}
            </Empty>
          </Card>
        ) : (
          <Table
            rowKey="id"
            columns={columns}
            dataSource={visible}
            loading={loading}
            pagination={visible.length > 50 ? { pageSize: 50 } : false}
            onRow={(s) => ({
              onClick: () => navigate(`/teacher/students/${s.id}`),
              style: { cursor: "pointer" },
            })}
            locale={{ emptyText: "No students match this filter." }}
            scroll={{ x: true }}
          />
        )}
      </Space>

      <AddStudentModal
        open={adding}
        onClose={() => setAdding(false)}
        onAdded={() => load()}
      />
    </TeacherLayout>
  );
};

export default ClassOverview;
