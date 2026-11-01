import { useEffect, useState } from 'react';
import { Alert, Button, Card, Empty, Form, Input, Modal, Segmented, Select, Space, Table, Tag, Typography } from 'antd';
import { useAuth } from '../contexts/AuthContext';

type ProblemEvent = {
  event_id: string; event_type: string; note: string | null; from_status: string | null;
  to_status: string | null; version: string | null; actor_name: string | null; created_at: string;
};
type Problem = {
  problem_id: string; title: string; description: string; severity: string; area: string | null;
  status: string; reported_version: string; reported_env: string; reporter_name: string | null;
  assignee_name: string | null; fixed_in_version: string | null; reporter_person_id: string;
  updated_at: string; reported_at: string; events?: ProblemEvent[];
};
type Version = { version: string; env: string; commit: string };

const SEVERITY_COLOR: Record<string, string> = { blocker: 'red', major: 'volcano', normal: 'blue', minor: 'default' };
const STATUS_COLOR: Record<string, string> = {
  open: 'red', reopened: 'orange', fixed_pending_retest: 'gold',
  closed: 'green', closed_wontfix: 'default', closed_duplicate: 'default', closed_notabug: 'default',
};
const STATUS_LABEL: Record<string, string> = {
  open: 'Open', reopened: 'Reopened', fixed_pending_retest: 'Awaiting re-test', closed: 'Closed',
  closed_wontfix: "Closed · won't fix", closed_duplicate: 'Closed · duplicate', closed_notabug: 'Closed · not a bug',
};

export default function KivaProblems() {
  const { authRequest } = useAuth();
  const [problems, setProblems] = useState<Problem[]>([]);
  const [retests, setRetests] = useState<Problem[]>([]);
  const [version, setVersion] = useState<Version | null>(null);
  const [myPersonId, setMyPersonId] = useState('');
  const [isDeveloper, setIsDeveloper] = useState(false);
  const [statusFilter, setStatusFilter] = useState('open');
  const [mineOnly, setMineOnly] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);
  const [detail, setDetail] = useState<Problem | null>(null);
  const [reportForm] = Form.useForm();
  const [fixForm] = Form.useForm();
  const [comment, setComment] = useState('');

  const load = async () => {
    try {
      const params = new URLSearchParams();
      if (statusFilter !== 'all') params.set('status', statusFilter);
      if (mineOnly) params.set('mine', 'true');
      const [p, r, v, me] = await Promise.all([
        authRequest.get(`/api/kiva/problems?${params.toString()}`),
        authRequest.get('/api/kiva/retests/mine'),
        authRequest.get('/api/kiva/version'),
        authRequest.get('/api/kiva/me'),
      ]);
      setProblems(p.data); setRetests(r.data); setVersion(v.data);
      setMyPersonId(me.data.person.person_id);
      setIsDeveloper((me.data.person.roles || []).includes('developer'));
      setError('');
    } catch (e: any) { setError(e.response?.data?.detail || 'Could not load the problem tracker.'); }
  };
  useEffect(() => { void load(); }, [statusFilter, mineOnly]);

  const perform = async (fn: () => Promise<any>) => {
    setBusy(true);
    try { await fn(); await load(); setError(''); }
    catch (e: any) { setError(e.response?.data?.detail || 'The action could not be completed.'); }
    finally { setBusy(false); }
  };

  const openDetail = async (problem: Problem) => {
    const full = await authRequest.get(`/api/kiva/problems/${problem.problem_id}`);
    setDetail(full.data); setComment('');
  };
  const refreshDetail = async (id: string) => {
    const full = await authRequest.get(`/api/kiva/problems/${id}`);
    setDetail(full.data);
  };

  const submitReport = () => perform(async () => {
    const v = await reportForm.validateFields();
    await authRequest.post('/api/kiva/problems', v);
    reportForm.resetFields(); setReportOpen(false);
  });
  const addComment = (id: string) => perform(async () => {
    if (!comment.trim()) return;
    await authRequest.post(`/api/kiva/problems/${id}/comment`, { note: comment.trim() });
    setComment(''); await refreshDetail(id);
  });
  const markFixed = (id: string) => perform(async () => {
    const v = await fixForm.validateFields();
    await authRequest.patch(`/api/kiva/problems/${id}`, { action: 'mark_fixed', version: v.version, note: v.note || undefined });
    fixForm.resetFields(); await refreshDetail(id);
  });
  const closeProblem = (id: string, reason: string) => perform(async () => {
    await authRequest.patch(`/api/kiva/problems/${id}`, { action: 'close', reason });
    await refreshDetail(id);
  });
  const retest = (id: string, result: string, note?: string) => perform(async () => {
    await authRequest.post(`/api/kiva/problems/${id}/retest`, { result, note });
    if (detail?.problem_id === id) await refreshDetail(id);
  });

  const columns = [
    { title: 'Problem', dataIndex: 'title', render: (t: string, r: Problem) => <a onClick={() => void openDetail(r)}>{t}</a> },
    { title: 'Severity', dataIndex: 'severity', render: (s: string) => <Tag color={SEVERITY_COLOR[s]}>{s}</Tag> },
    { title: 'Status', dataIndex: 'status', render: (s: string) => <Tag color={STATUS_COLOR[s]}>{STATUS_LABEL[s] || s}</Tag> },
    { title: 'Area', dataIndex: 'area', render: (a: string | null) => a || '—' },
    { title: 'Version', render: (_: unknown, r: Problem) => <Typography.Text type="secondary">{r.reported_version} · {r.reported_env}</Typography.Text> },
    { title: 'Reporter', dataIndex: 'reporter_name', render: (n: string | null) => n || '—' },
  ];

  const isReporter = detail && detail.reporter_person_id === myPersonId;
  const detailOpenState = detail && (detail.status === 'open' || detail.status === 'reopened');
  const detailAwaitingRetest = detail && detail.status === 'fixed_pending_retest';

  return <div>
    {error && <Alert type="error" message={error} closable onClose={() => setError('')} style={{ marginBottom: 16 }} />}

    <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }} wrap>
      <Space wrap>
        <Segmented value={statusFilter} onChange={v => setStatusFilter(String(v))}
          options={[{ label: 'Open', value: 'open' }, { label: 'Awaiting re-test', value: 'fixed_pending_retest' },
                    { label: 'Closed', value: 'closed' }, { label: 'All', value: 'all' }]} />
        <Button type={mineOnly ? 'primary' : 'default'} onClick={() => setMineOnly(m => !m)}>Only mine</Button>
      </Space>
      <Space>
        {version && <Tag color="blue">{version.version} · {version.env}</Tag>}
        <Button type="primary" onClick={() => { reportForm.resetFields(); setReportOpen(true); }}>Report a problem</Button>
      </Space>
    </Space>

    {retests.length > 0 && <Card size="small" style={{ marginBottom: 16, borderColor: '#faad14' }}
      title={`${retests.length} fix${retests.length > 1 ? 'es' : ''} awaiting your re-test`}>
      <Space direction="vertical" style={{ width: '100%' }}>
        {retests.map(p => <div key={p.problem_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
          <span><a onClick={() => void openDetail(p)}>{p.title}</a> <Typography.Text type="secondary">fixed in {p.fixed_in_version}</Typography.Text></span>
          <Space>
            <Button size="small" type="primary" loading={busy} onClick={() => retest(p.problem_id, 'confirmed')}>Confirm fixed</Button>
            <Button size="small" danger loading={busy} onClick={() => retest(p.problem_id, 'still_broken')}>Still broken</Button>
            <Button size="small" loading={busy} onClick={() => retest(p.problem_id, 'new')}>It's different now</Button>
          </Space>
        </div>)}
      </Space>
    </Card>}

    <Table rowKey="problem_id" dataSource={problems} columns={columns} pagination={{ pageSize: 12 }}
      locale={{ emptyText: <Empty description="No problems in this view" /> }} />

    <Modal open={reportOpen} title="Report a problem" onCancel={() => setReportOpen(false)} onOk={submitReport}
      confirmLoading={busy} okText="Report">
      <Typography.Paragraph type="secondary">
        Auto-tagged with {version ? `${version.version} · ${version.env}` : 'the current version'} · as you. Just describe the problem.
      </Typography.Paragraph>
      <Form autoComplete="off" form={reportForm} layout="vertical" initialValues={{ severity: 'normal' }}>
        <Form.Item name="title" label="What went wrong?" rules={[{ required: true, message: 'Give it a short title.' }]}>
          <Input placeholder="e.g. Voice cuts out mid-sentence" /></Form.Item>
        <Form.Item name="description" label="Details (steps, what you expected)"><Input.TextArea rows={4} /></Form.Item>
        <Form.Item name="severity" label="Severity">
          <Select options={['blocker', 'major', 'normal', 'minor'].map(s => ({ value: s, label: s }))} /></Form.Item>
        <Form.Item name="area" label="Area (optional)"><Input placeholder="voice | lipsync | auth | flow | ui | ..." /></Form.Item>
      </Form>
    </Modal>

    <Modal open={!!detail} title={detail?.title} width={720} footer={null} onCancel={() => setDetail(null)}>
      {detail && <Space direction="vertical" style={{ width: '100%' }} size={16}>
        <Space wrap>
          <Tag color={SEVERITY_COLOR[detail.severity]}>{detail.severity}</Tag>
          <Tag color={STATUS_COLOR[detail.status]}>{STATUS_LABEL[detail.status] || detail.status}</Tag>
          {detail.area && <Tag>{detail.area}</Tag>}
          <Typography.Text type="secondary">{detail.reported_version} · {detail.reported_env} · by {detail.reporter_name || '—'}</Typography.Text>
        </Space>
        {detail.description && <Typography.Paragraph style={{ whiteSpace: 'pre-wrap' }}>{detail.description}</Typography.Paragraph>}

        <Card size="small" title="Discussion & history" styles={{ body: { maxHeight: 280, overflowY: 'auto' } }}>
          {(detail.events || []).map(e => <div key={e.event_id} style={{ marginBottom: 10 }}>
            {e.event_type === 'commented'
              ? <div><b>{e.actor_name || '—'}:</b> <span style={{ whiteSpace: 'pre-wrap' }}>{e.note}</span></div>
              : <Typography.Text type="secondary">— {e.actor_name || '—'} {EVENT_VERB[e.event_type] || e.event_type}{e.version ? ` (${e.version})` : ''}{e.note ? `: ${e.note}` : ''}</Typography.Text>}
            <div><Typography.Text type="secondary" style={{ fontSize: 11 }}>{new Date(e.created_at + 'Z').toLocaleString()}</Typography.Text></div>
          </div>)}
        </Card>

        <Space.Compact style={{ width: '100%' }}>
          <Input value={comment} onChange={e => setComment(e.target.value)} placeholder="Ask a question or add a note…"
            onPressEnter={() => addComment(detail.problem_id)} />
          <Button type="primary" loading={busy} onClick={() => addComment(detail.problem_id)}>Send</Button>
        </Space.Compact>

        {isReporter && detailAwaitingRetest && <Space wrap>
          <Button type="primary" loading={busy} onClick={() => retest(detail.problem_id, 'confirmed')}>Confirm fixed</Button>
          <Button danger loading={busy} onClick={() => retest(detail.problem_id, 'still_broken')}>Still broken</Button>
          <Button loading={busy} onClick={() => retest(detail.problem_id, 'new')}>It's different now</Button>
        </Space>}

        {isDeveloper && detailOpenState && <Card size="small" title="Developer">
          <Space direction="vertical" style={{ width: '100%' }}>
            <Form autoComplete="off" form={fixForm} layout="inline" initialValues={{ version: version?.version }}>
              <Form.Item name="version" rules={[{ required: true, message: 'Which drop?' }]}><Input placeholder="fixed in drop…" style={{ width: 220 }} /></Form.Item>
              <Form.Item name="note"><Input placeholder="note (optional)" style={{ width: 200 }} /></Form.Item>
              <Button type="primary" loading={busy} onClick={() => markFixed(detail.problem_id)}>Mark fixed</Button>
            </Form>
            <Space wrap>
              <Button size="small" loading={busy} onClick={() => closeProblem(detail.problem_id, 'wontfix')}>Won't fix</Button>
              <Button size="small" loading={busy} onClick={() => closeProblem(detail.problem_id, 'duplicate')}>Duplicate</Button>
              <Button size="small" loading={busy} onClick={() => closeProblem(detail.problem_id, 'notabug')}>Not a bug</Button>
            </Space>
          </Space>
        </Card>}
      </Space>}
    </Modal>
  </div>;
}

const EVENT_VERB: Record<string, string> = {
  reported: 'reported this', assigned: 'assigned', marked_fixed: 'marked fixed',
  retest_requested: 'requested a re-test', confirmed_fixed: 'confirmed the fix',
  still_broken: 'said still broken', reopened: 'reopened', closed: 'closed',
};
