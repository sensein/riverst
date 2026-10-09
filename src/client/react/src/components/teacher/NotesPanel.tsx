/**
 * NotesPanel.tsx
 * Private, timestamped teacher notes on a student or a session.
 */

import React, { useCallback, useEffect, useState } from "react";
import {
  Alert,
  App,
  Button,
  Card,
  Input,
  List,
  Popconfirm,
  Space,
  Typography,
} from "antd";
import { useAuth } from "../../contexts/AuthContext";
import { formatRelative } from "./labels";
import type { Note } from "./types";

interface NotesPanelProps {
  targetType: "student" | "session";
  targetId: string;
}

const NotesPanel: React.FC<NotesPanelProps> = ({ targetType, targetId }) => {
  const { authRequest } = useAuth();
  const { message } = App.useApp();
  const [notes, setNotes] = useState<Note[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState<{ id: string; body: string } | null>(
    null,
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await authRequest.get("/api/teacher/notes", {
        params: { target_type: targetType, target_id: targetId },
      });
      setNotes(res.data.notes);
      setLoadFailed(false);
    } catch {
      setLoadFailed(true);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetType, targetId]);

  useEffect(() => {
    load();
  }, [load]);

  const add = async () => {
    if (!draft.trim()) return;
    setSaving(true);
    try {
      const res = await authRequest.post("/api/teacher/notes", {
        target_type: targetType,
        target_id: targetId,
        body: draft.trim(),
      });
      setNotes((prev) => [res.data, ...prev]);
      setDraft("");
    } catch {
      message.error("We couldn't save the note. Try again.");
    } finally {
      setSaving(false);
    }
  };

  const saveEdit = async () => {
    if (!editing || !editing.body.trim()) return;
    try {
      const res = await authRequest.patch(`/api/teacher/notes/${editing.id}`, {
        body: editing.body.trim(),
      });
      setNotes((prev) => prev.map((n) => (n.id === editing.id ? res.data : n)));
      setEditing(null);
    } catch {
      message.error("We couldn't update the note. Try again.");
    }
  };

  const remove = async (id: string) => {
    try {
      await authRequest.delete(`/api/teacher/notes/${id}`);
      setNotes((prev) => prev.filter((n) => n.id !== id));
    } catch {
      message.error("We couldn't delete the note. Try again.");
    }
  };

  return (
    <Card
      title="Notes"
      extra={
        <Typography.Text type="secondary">
          Only you can see these notes.
        </Typography.Text>
      }
    >
      {loadFailed && (
        <Alert
          type="error"
          showIcon
          message="We couldn't load your notes."
          action={
            <Button size="small" onClick={load}>
              Try again
            </Button>
          }
          style={{ marginBottom: 16 }}
        />
      )}
      <Space.Compact
        style={{ width: "100%", marginBottom: 16 }}
        direction="vertical"
      >
        <Input.TextArea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          maxLength={2000}
          autoSize={{ minRows: 2, maxRows: 6 }}
          placeholder="Add a note, for example: was tired today"
        />
        <Button
          type="primary"
          onClick={add}
          loading={saving}
          disabled={!draft.trim()}
          style={{ alignSelf: "flex-end" }}
        >
          Add note
        </Button>
      </Space.Compact>
      <List
        loading={loading}
        dataSource={notes}
        locale={{ emptyText: "No notes yet." }}
        renderItem={(note) => (
          <List.Item
            actions={
              editing?.id === note.id
                ? [
                    <Button key="save" type="link" onClick={saveEdit}>
                      Save
                    </Button>,
                    <Button
                      key="cancel"
                      type="link"
                      onClick={() => setEditing(null)}
                    >
                      Cancel
                    </Button>,
                  ]
                : [
                    <Button
                      key="edit"
                      type="link"
                      onClick={() =>
                        setEditing({ id: note.id, body: note.body })
                      }
                    >
                      Edit
                    </Button>,
                    <Popconfirm
                      key="delete"
                      title="Delete this note?"
                      okText="Delete"
                      onConfirm={() => remove(note.id)}
                    >
                      <Button type="link" danger>
                        Delete
                      </Button>
                    </Popconfirm>,
                  ]
            }
          >
            {editing?.id === note.id ? (
              <Input.TextArea
                value={editing.body}
                maxLength={2000}
                autoSize={{ minRows: 2, maxRows: 6 }}
                onChange={(e) =>
                  setEditing({ id: note.id, body: e.target.value })
                }
              />
            ) : (
              <List.Item.Meta
                title={
                  <Typography.Text
                    style={{ whiteSpace: "pre-wrap", fontWeight: 400 }}
                  >
                    {note.body}
                  </Typography.Text>
                }
                description={formatRelative(note.created_at)}
              />
            )}
          </List.Item>
        )}
      />
    </Card>
  );
};

export default NotesPanel;
