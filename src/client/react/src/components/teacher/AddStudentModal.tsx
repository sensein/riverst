/**
 * AddStudentModal.tsx
 * Adds a student, then shows their code and link so the teacher can share them.
 */

import React, { useState } from "react";
import { Button, Form, Input, Modal, Space, Typography } from "antd";
import { useAuth } from "../../contexts/AuthContext";
import { httpStatus } from "../../utils/studentCode";
import StudentCode from "./StudentCode";
import type { StudentBase } from "./types";

interface AddStudentModalProps {
  open: boolean;
  onClose: () => void;
  /** Called after a student is created so the class list can refresh. */
  onAdded: (student: StudentBase) => void;
}

const AddStudentModal: React.FC<AddStudentModalProps> = ({
  open,
  onClose,
  onAdded,
}) => {
  const { authRequest } = useAuth();
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<StudentBase | null>(null);

  const close = () => {
    form.resetFields();
    setCreated(null);
    setError(null);
    onClose();
  };

  const submit = async ({ display_name }: { display_name: string }) => {
    setSaving(true);
    setError(null);
    try {
      const res = await authRequest.post("/api/teacher/students", {
        display_name,
      });
      setCreated(res.data);
      onAdded(res.data);
    } catch (err) {
      const detail =
        httpStatus(err) === 422 ? "Enter a name of up to 40 characters." : null;
      setError(detail ?? "We couldn't add the student. Try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      title={created ? `${created.display_name} was added` : "Add a student"}
      onCancel={close}
      destroyOnHidden
      footer={
        created ? (
          <Space>
            <Button
              onClick={() => {
                form.resetFields();
                setCreated(null);
              }}
            >
              Add another
            </Button>
            <Button type="primary" onClick={close}>
              Done
            </Button>
          </Space>
        ) : (
          <Space>
            <Button onClick={close}>Cancel</Button>
            <Button
              type="primary"
              loading={saving}
              onClick={() => form.submit()}
            >
              Add student
            </Button>
          </Space>
        )
      }
    >
      {created ? (
        <Space direction="vertical" size={12}>
          <Typography.Paragraph style={{ marginBottom: 0 }}>
            Give {created.display_name} this code, or send the link. They enter
            it when they start KIVA.
          </Typography.Paragraph>
          <StudentCode code={created.code} link={created.link} />
        </Space>
      ) : (
        <Form
          form={form}
          layout="vertical"
          onFinish={submit}
          requiredMark={false}
        >
          <Form.Item
            name="display_name"
            label="Student name"
            extra="First name or nickname only."
            rules={[
              {
                required: true,
                whitespace: true,
                message: "Enter the student’s name.",
              },
              { max: 40, message: "Use 40 characters or fewer." },
            ]}
            validateStatus={error ? "error" : undefined}
            help={error ?? undefined}
          >
            <Input autoFocus maxLength={40} />
          </Form.Item>
        </Form>
      )}
    </Modal>
  );
};

export default AddStudentModal;
