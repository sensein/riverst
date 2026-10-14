import { useEffect, useState } from 'react';
import { Alert, Button, Card, Checkbox, Form, Input, Modal, Popconfirm, Radio, Select, Space, Table, Tabs, Tag, Typography } from 'antd';
import { useAuth } from '../contexts/AuthContext';

type Person = { person_id: string; profile: Record<string, unknown>; roles: string[]; status: string };
type Study = { study_id: string; name: string; status: string; applications?: { application_key: string; enabled: number | boolean }[] };
type Application = { application_key: string; name: string; status: string };
type Session = { session_id: string; subject_person_id: string; study_id: string; status: string; created_at?: string; started_at?: string; ended_at?: string };
type Artifacts = { session_id: string; has_transcript: boolean; audio: { file: string; url: string }[] };

const ROLE_OPTIONS = [{ label: 'Learner / child', value: 'learner' }, { label: 'Guardian / parent', value: 'guardian' }, { label: 'Instructor / tutor', value: 'instructor' }, { label: 'Tester', value: 'tester' }, { label: 'Developer', value: 'developer' }];
// The app catalog a study can offer — mirrors the Create-study checklist in KivaWorkspace.
const APP_CATALOG = [{ value: 'listen_audiobooks', label: 'Listen to audiobooks' }, { value: 'vocabulary', label: 'Learning vocabulary' }, { value: 'esl', label: 'English (L2) — for Italian speakers' }, { value: 'isl', label: 'Italian (L2) — for English speakers' }];

export default function KivaAdmin({ onCreateStudy }: { onCreateStudy: () => void }) {
  const { authRequest } = useAuth();
  const [people, setPeople] = useState<Person[]>([]);
  const [studies, setStudies] = useState<Study[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [error, setError] = useState('');
  const [person, setPerson] = useState<Person | null | false>(false);
  const [study, setStudy] = useState<Study | null>(null);
  const [application, setApplication] = useState<Application | null>(null);
  const [addApplicationOpen, setAddApplicationOpen] = useState(false);
  const [linkOpen, setLinkOpen] = useState(false);
  const [enrollPerson, setEnrollPerson] = useState<Person | null>(null);
  const [addLearnerStudy, setAddLearnerStudy] = useState<Study | null>(null);
  const [personForm] = Form.useForm(); const [studyForm] = Form.useForm();
  const [appForm] = Form.useForm(); const [linkForm] = Form.useForm(); const [enrollForm] = Form.useForm(); const [learnerForm] = Form.useForm();
  const [busy, setBusy] = useState(false);
  const [showInactive, setShowInactive] = useState(false);
  const [detailStudy, setDetailStudy] = useState<Study | null>(null);
  const [learners, setLearners] = useState<Person[]>([]);
  const [sessionsByPerson, setSessionsByPerson] = useState<Record<string, Session[]>>({});
  const [viewSession, setViewSession] = useState<Session | null>(null);
  const [transcript, setTranscript] = useState<any>(null); // null = loading, false = unavailable, else data
  const [artifacts, setArtifacts] = useState<Artifacts | null>(null);
  const refresh = async () => {
    try {
      const [p, s, a] = await Promise.all([
        authRequest.get('/api/kiva/people?status=all'), authRequest.get('/api/kiva/studies'),
        authRequest.get('/api/kiva/applications?status=all'),
      ]);
      setPeople(p.data); setStudies(s.data); setApplications(a.data); setError('');
    } catch (e: any) { setError(e.response?.data?.detail || 'Could not load management data.'); }
  };
  useEffect(() => {
    void refresh();
    const handler = () => { void refresh(); };
    window.addEventListener('kiva:refresh-admin', handler);
    return () => window.removeEventListener('kiva:refresh-admin', handler);
  }, []);
  const perform = async (fn: () => Promise<void>) => { setBusy(true); try { await fn(); await refresh(); } catch (e: any) { setError(e.response?.data?.detail || 'The change could not be saved.'); } finally { setBusy(false); } };
  const savePerson = () => perform(async () => {
    const v = await personForm.validateFields();
    const profile_patch = { display_name: v.display_name, age: v.age || null, email: v.email || null };
    if (person) await authRequest.patch(`/api/kiva/people/${person.person_id}`, { roles: v.roles, profile_patch });
    else await authRequest.post('/api/kiva/people', { roles: v.roles, profile: profile_patch });
    setPerson(false); personForm.resetFields();
  });
  const saveStudy = () => perform(async () => {
    const v = await studyForm.validateFields(); if (!study) return;
    await authRequest.patch(`/api/kiva/studies/${study.study_id}`, { name: v.name, status: v.status });
    const selected: string[] = v.applications || [];
    for (const app of APP_CATALOG) {
      await authRequest.post('/api/kiva/applications', { application_key: app.value, name: app.label });
      await authRequest.post(`/api/kiva/studies/${study.study_id}/applications`, { application_key: app.value, config: {}, enabled: selected.includes(app.value) });
    }
    setStudy(null);
  });
  const saveApplication = () => perform(async () => { const v = await appForm.validateFields(); if (!application) return; await authRequest.patch(`/api/kiva/applications/${application.application_key}`, v); setApplication(null); });
  const createApplication = () => perform(async () => { const v = await appForm.validateFields(); await authRequest.post('/api/kiva/applications', v); setAddApplicationOpen(false); appForm.resetFields(); });
  const linkPeople = () => perform(async () => { const v = await linkForm.validateFields(); await authRequest.post('/api/kiva/guardian-links', { guardian_person_id: v.guardian, learner_person_id: v.learner }); setLinkOpen(false); linkForm.resetFields(); });
  const enrollLearner = () => perform(async () => { const v = await enrollForm.validateFields(); await authRequest.post(`/api/kiva/studies/${v.study_id}/learners`, { learner_person_id: enrollPerson?.person_id }); setEnrollPerson(null); enrollForm.resetFields(); });
  const addLearner = () => perform(async () => { const v = await learnerForm.validateFields(); if (!addLearnerStudy) return; const body = v.mode === 'existing' ? { learner_person_id: v.learner_person_id } : { profile_patch: { display_name: v.display_name, age: v.age ? Number(v.age) : null } }; await authRequest.post(`/api/kiva/studies/${addLearnerStudy.study_id}/learners`, body); setAddLearnerStudy(null); learnerForm.resetFields(); window.dispatchEvent(new Event('kiva:refresh-admin')); });
  const openDetail = async (s: Study) => {
    setDetailStudy(s); setLearners([]); setSessionsByPerson({});
    try { const r = await authRequest.get(`/api/kiva/people?role=learner&study_id=${s.study_id}`); setLearners(r.data); }
    catch (e: any) { setError(e.response?.data?.detail || 'Could not load enrolled learners.'); }
  };
  const loadSessions = async (personId: string) => {
    if (!detailStudy) return;
    try { const r = await authRequest.get(`/api/kiva/subjects/${personId}/sessions?study_id=${detailStudy.study_id}`); setSessionsByPerson(m => ({ ...m, [personId]: r.data })); }
    catch (e: any) { setError(e.response?.data?.detail || 'Could not load sessions.'); setSessionsByPerson(m => ({ ...m, [personId]: [] })); }
  };
  const openSessionView = async (s: Session) => {
    setViewSession(s); setTranscript(null); setArtifacts(null);
    const [t, a] = await Promise.allSettled([
      authRequest.get(`/api/kiva/sessions/${s.session_id}/transcript`),
      authRequest.get(`/api/kiva/sessions/${s.session_id}/artifacts`),
    ]);
    setTranscript(t.status === 'fulfilled' ? t.value.data : false);
    setArtifacts(a.status === 'fulfilled' ? a.value.data : { session_id: s.session_id, has_transcript: false, audio: [] });
  };
  return <>
    {error && <Alert type="error" message={error} closable onClose={() => setError('')} style={{ marginBottom: 16 }} />}
    <Tabs items={[
      { key: 'studies', label: 'Studies', children: <Card title="Studies you instruct" extra={<Button onClick={onCreateStudy}>Add study</Button>}><Table rowKey="study_id" dataSource={[...studies].sort((a, b) => a.name.localeCompare(b.name))} pagination={false} columns={[{ title: 'Name', dataIndex: 'name', render: (v: string, row: Study) => <a onClick={() => void openDetail(row)}>{v}</a> }, { title: 'Status', dataIndex: 'status', render: (v: string) => <Tag>{v}</Tag> }, { title: 'Actions', render: (_: unknown, row: Study) => <Space><Button onClick={() => void openDetail(row)}>View</Button><Button type="primary" onClick={() => { learnerForm.resetFields(); setAddLearnerStudy(row); }}>Add learner</Button><Button onClick={() => { setStudy(row); studyForm.setFieldsValue({ name: row.name, status: row.status, applications: (row.applications || []).filter(a => a.enabled).map(a => a.application_key) }); }}>Edit</Button><Popconfirm title="Close this study?" onConfirm={() => void perform(async () => { await authRequest.delete(`/api/kiva/studies/${row.study_id}`); })}><Button danger>Close</Button></Popconfirm></Space> }]} /></Card> },
      { key: 'people', label: 'People', children: <Card title="People" extra={<Space><Button type="primary" onClick={() => { personForm.resetFields(); setPerson(null); }}>Add person</Button><Button onClick={() => setLinkOpen(true)}>Add child to adult</Button><Button onClick={() => setShowInactive(v => !v)}>{showInactive ? 'Hide inactive' : 'Show inactive'}</Button></Space>}><Typography.Paragraph type="secondary">One person can have multiple roles. Child = learner; parent = guardian; tutor = instructor. Person details are study-independent.</Typography.Paragraph><Table rowKey="person_id" dataSource={(showInactive ? [...people] : people.filter(p => p.status === 'active')).sort((a, b) => String(a.profile.display_name || '').localeCompare(String(b.profile.display_name || '')))} pagination={{ pageSize: 8 }} columns={[{ title: 'Name', render: (_: unknown, r: Person) => String(r.profile.display_name || 'Unnamed') }, { title: 'Roles', dataIndex: 'roles', render: (rs: string[]) => rs.map(r => <Tag key={r}>{r}</Tag>) }, { title: 'Age', render: (_: unknown, r: Person) => String(r.profile.age || '—') }, { title: 'Email', render: (_: unknown, r: Person) => String(r.profile.email || '—') }, { title: 'Status', dataIndex: 'status' }, { title: 'Actions', render: (_: unknown, r: Person) => <Space><Button onClick={() => { setPerson(r); personForm.setFieldsValue({ ...r.profile, roles: r.roles }); }}>Edit</Button>{r.roles.includes('learner') && <><Button onClick={() => { linkForm.setFieldsValue({ learner: r.person_id }); setLinkOpen(true); }}>Link adult</Button><Button onClick={() => { setEnrollPerson(r); enrollForm.resetFields(); }}>Enroll</Button></>}<Popconfirm title="Deactivate this person?" onConfirm={() => void perform(async () => { await authRequest.delete(`/api/kiva/people/${r.person_id}`); })}><Button danger>Deactivate</Button></Popconfirm></Space> }]} /></Card> },
      { key: 'applications', label: 'Applications', children: <Card title="Applications" extra={<Button type="primary" onClick={() => { appForm.resetFields(); setAddApplicationOpen(true); }}>Add application</Button>}><Table rowKey="application_key" dataSource={[...applications].sort((a, b) => a.name.localeCompare(b.name))} pagination={false} columns={[{ title: 'Name', dataIndex: 'name' }, { title: 'Key', dataIndex: 'application_key' }, { title: 'Status', dataIndex: 'status' }, { title: 'Actions', render: (_: unknown, row: Application) => <Space><Button onClick={() => { setApplication(row); appForm.setFieldsValue(row); }}>Edit</Button><Popconfirm title="Deactivate this application?" onConfirm={() => void perform(async () => { await authRequest.delete(`/api/kiva/applications/${row.application_key}`); })}><Button danger>Deactivate</Button></Popconfirm></Space> }]} /></Card> },
    ]} />
    <Modal open={person !== false} title={person ? 'Edit person' : 'Add person'} onCancel={() => setPerson(false)} onOk={savePerson} confirmLoading={busy}><Form autoComplete="off" form={personForm} layout="vertical"><Form.Item name="display_name" label="Name" rules={[{ required: true }]}><Input /></Form.Item><Form.Item name="roles" label="Roles" rules={[{ required: true }]}><Checkbox.Group options={ROLE_OPTIONS} /></Form.Item><Form.Item name="age" label="Age (optional; usually for learners)"><Input type="number" /></Form.Item><Form.Item name="email" label="Email (optional; usually for adults)"><Input type="email" /></Form.Item></Form></Modal>
    <Modal open={!!study} title="Edit study" onCancel={() => setStudy(null)} onOk={saveStudy} confirmLoading={busy}><Form autoComplete="off" form={studyForm} layout="vertical"><Form.Item name="name" label="Name" rules={[{ required: true }]}><Input /></Form.Item><Form.Item name="status" label="Status"><Select options={['draft', 'active', 'closed'].map(value => ({ value }))} /></Form.Item><Form.Item name="applications" label="Applications"><Checkbox.Group options={APP_CATALOG} /></Form.Item></Form></Modal>
    <Modal open={!!application} title="Edit application" onCancel={() => setApplication(null)} onOk={saveApplication} confirmLoading={busy}><Form autoComplete="off" form={appForm} layout="vertical"><Form.Item name="name" label="Name" rules={[{ required: true }]}><Input /></Form.Item><Form.Item name="status" label="Status"><Select options={['active', 'inactive'].map(value => ({ value }))} /></Form.Item></Form></Modal>
    <Modal open={addApplicationOpen} title="Add application" onCancel={() => setAddApplicationOpen(false)} onOk={createApplication} confirmLoading={busy}><Form autoComplete="off" form={appForm} layout="vertical"><Form.Item name="application_key" label="Application key" rules={[{ required: true }]}><Input placeholder="e.g. reading_comprehension" /></Form.Item><Form.Item name="name" label="Display name" rules={[{ required: true }]}><Input placeholder="e.g. Reading comprehension" /></Form.Item></Form></Modal>
    <Modal open={linkOpen} title="Add child to adult" onCancel={() => setLinkOpen(false)} onOk={linkPeople} confirmLoading={busy}><Form autoComplete="off" form={linkForm} layout="vertical"><Form.Item name="guardian" label="Adult / guardian" rules={[{ required: true }]}><Select options={people.filter(p => p.status === 'active' && p.roles.includes('guardian')).map(p => ({ value: p.person_id, label: String(p.profile.display_name || p.person_id) })).sort((a, b) => a.label.localeCompare(b.label))} /></Form.Item><Form.Item name="learner" label="Child / learner" rules={[{ required: true }]}><Select options={people.filter(p => p.status === 'active' && p.roles.includes('learner')).map(p => ({ value: p.person_id, label: String(p.profile.display_name || p.person_id) })).sort((a, b) => a.label.localeCompare(b.label))} /></Form.Item></Form></Modal>
    <Modal open={!!enrollPerson} title="Enroll learner in a study" onCancel={() => setEnrollPerson(null)} onOk={enrollLearner} confirmLoading={busy}><Form autoComplete="off" form={enrollForm} layout="vertical"><Form.Item label="Learner"><Input value={String(enrollPerson?.profile.display_name || '')} disabled /></Form.Item><Form.Item name="study_id" label="Study" rules={[{ required: true }]}><Select options={studies.filter(s => s.status !== 'closed').map(s => ({ value: s.study_id, label: s.name })).sort((a, b) => a.label.localeCompare(b.label))} /></Form.Item></Form></Modal>
    <Modal open={!!detailStudy} title={detailStudy ? `${detailStudy.name} — enrolled learners` : ''} footer={null} width={760} onCancel={() => setDetailStudy(null)} destroyOnClose>
      {!learners.length ? <Typography.Text type="secondary">No learners enrolled in this study yet.</Typography.Text> :
        <Table rowKey="person_id" pagination={false} dataSource={[...learners].sort((a, b) => String(a.profile.display_name || '').localeCompare(String(b.profile.display_name || '')))}
          columns={[{ title: 'Learner', render: (_: unknown, r: Person) => String(r.profile.display_name || 'Unnamed') }, { title: 'Age', render: (_: unknown, r: Person) => String(r.profile.age || '—') }]}
          expandable={{
            onExpand: (expanded, r) => { if (expanded && !sessionsByPerson[r.person_id]) void loadSessions(r.person_id); },
            expandedRowRender: (r: Person) => {
              const ss = sessionsByPerson[r.person_id];
              if (!ss) return <Typography.Text type="secondary">Loading sessions…</Typography.Text>;
              if (!ss.length) return <Typography.Text type="secondary">No sessions yet.</Typography.Text>;
              return <Table rowKey="session_id" size="small" pagination={false} dataSource={[...ss].sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')))}
                columns={[
                  { title: 'Started', render: (_: unknown, s: Session) => String(s.started_at || s.created_at || '—') },
                  { title: 'Ended', render: (_: unknown, s: Session) => String(s.ended_at || '—') },
                  { title: 'Status', dataIndex: 'status', render: (v: string) => <Tag>{v}</Tag> },
                  { title: '', render: (_: unknown, s: Session) => <Button size="small" onClick={() => void openSessionView(s)}>View</Button> },
                ]} />;
            },
          }} />}
    </Modal>
    <Modal open={!!viewSession} title={viewSession ? `Session ${viewSession.session_id.slice(0, 8)} · ${viewSession.status}` : ''} footer={null} width={720} onCancel={() => setViewSession(null)} destroyOnClose>
      <Typography.Title level={5}>Transcript</Typography.Title>
      {transcript === null ? <Typography.Text type="secondary">Loading…</Typography.Text> :
        transcript === false ? <Typography.Text type="secondary">No transcript available for this session.</Typography.Text> :
          Array.isArray(transcript) ? <div style={{ maxHeight: 300, overflow: 'auto', background: '#fafafa', padding: 12, borderRadius: 6 }}>{transcript.map((turn: any, i: number) => <p key={i} style={{ margin: '4px 0' }}><b>{turn.role || turn.speaker || '?'}:</b> {turn.content ?? turn.text ?? JSON.stringify(turn)}</p>)}</div> :
            <pre style={{ maxHeight: 300, overflow: 'auto', background: '#fafafa', padding: 12, borderRadius: 6 }}>{JSON.stringify(transcript, null, 2)}</pre>}
      <Typography.Title level={5} style={{ marginTop: 16 }}>Audio</Typography.Title>
      {!artifacts ? <Typography.Text type="secondary">Loading…</Typography.Text> :
        !artifacts.audio.length ? <Typography.Text type="secondary">No audio recordings for this session.</Typography.Text> :
          artifacts.audio.map(a => <div key={a.file} style={{ marginBottom: 8 }}><div style={{ fontSize: 12, color: '#888' }}>{a.file}</div><audio controls src={a.url} style={{ width: '100%' }} /></div>)}
    </Modal>
    <Modal open={!!addLearnerStudy} title={`Add a learner to ${addLearnerStudy?.name || ''}`} onCancel={() => setAddLearnerStudy(null)} onOk={addLearner} confirmLoading={busy} okText="Add learner"><Form autoComplete="off" form={learnerForm} layout="vertical" initialValues={{ mode: 'new' }}><Form.Item name="mode"><Radio.Group optionType="button" options={[{ label: 'New learner', value: 'new' }, { label: 'Existing learner', value: 'existing' }]} /></Form.Item><Form.Item noStyle shouldUpdate={(prev, cur) => prev.mode !== cur.mode}>{({ getFieldValue }) => getFieldValue('mode') === 'existing' ? <Form.Item name="learner_person_id" label="Learner" rules={[{ required: true, message: 'Pick a learner.' }]}><Select options={people.filter(p => p.status === 'active' && p.roles.includes('learner')).map(p => ({ value: p.person_id, label: String(p.profile.display_name || p.person_id) })).sort((a, b) => a.label.localeCompare(b.label))} /></Form.Item> : <><Form.Item name="display_name" label="Name" rules={[{ required: true, message: 'Enter a name.' }]}><Input placeholder="e.g. Student 2" /></Form.Item><Form.Item name="age" label="Age (optional)"><Input type="number" /></Form.Item></>}</Form.Item></Form></Modal>
  </>;
}
