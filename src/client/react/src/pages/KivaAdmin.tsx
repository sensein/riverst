import { useEffect, useState } from 'react';
import { Alert, Button, Card, Form, Input, Modal, Popconfirm, Radio, Select, Space, Table, Tabs, Tag, Typography } from 'antd';
import { useAuth } from '../contexts/AuthContext';

type Person = { person_id: string; profile: Record<string, unknown>; roles: string[]; status: string };
type Study = { study_id: string; name: string; status: string };
type Application = { application_key: string; name: string; status: string };

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
  const saveStudy = () => perform(async () => { const v = await studyForm.validateFields(); if (!study) return; await authRequest.patch(`/api/kiva/studies/${study.study_id}`, v); setStudy(null); });
  const saveApplication = () => perform(async () => { const v = await appForm.validateFields(); if (!application) return; await authRequest.patch(`/api/kiva/applications/${application.application_key}`, v); setApplication(null); });
  const createApplication = () => perform(async () => { const v = await appForm.validateFields(); await authRequest.post('/api/kiva/applications', v); setAddApplicationOpen(false); appForm.resetFields(); });
  const linkPeople = () => perform(async () => { const v = await linkForm.validateFields(); await authRequest.post('/api/kiva/guardian-links', { guardian_person_id: v.guardian, learner_person_id: v.learner }); setLinkOpen(false); linkForm.resetFields(); });
  const enrollLearner = () => perform(async () => { const v = await enrollForm.validateFields(); await authRequest.post(`/api/kiva/studies/${v.study_id}/learners`, { learner_person_id: enrollPerson?.person_id }); setEnrollPerson(null); enrollForm.resetFields(); });
  const addLearner = () => perform(async () => { const v = await learnerForm.validateFields(); if (!addLearnerStudy) return; const body = v.mode === 'existing' ? { learner_person_id: v.learner_person_id } : { profile_patch: { display_name: v.display_name, age: v.age ? Number(v.age) : null } }; await authRequest.post(`/api/kiva/studies/${addLearnerStudy.study_id}/learners`, body); setAddLearnerStudy(null); learnerForm.resetFields(); window.dispatchEvent(new Event('kiva:refresh-admin')); });
  return <>
    {error && <Alert type="error" message={error} closable onClose={() => setError('')} style={{ marginBottom: 16 }} />}
    <Tabs items={[
      { key: 'studies', label: 'Studies', children: <Card title="Studies you instruct" extra={<Button onClick={onCreateStudy}>Add study</Button>}><Table rowKey="study_id" dataSource={studies} pagination={false} columns={[{ title: 'Name', dataIndex: 'name' }, { title: 'Status', dataIndex: 'status', render: (v: string) => <Tag>{v}</Tag> }, { title: 'Actions', render: (_: unknown, row: Study) => <Space><Button type="primary" onClick={() => { learnerForm.resetFields(); setAddLearnerStudy(row); }}>Add learner</Button><Button onClick={() => { setStudy(row); studyForm.setFieldsValue(row); }}>Edit</Button><Popconfirm title="Close this study?" onConfirm={() => void perform(async () => { await authRequest.delete(`/api/kiva/studies/${row.study_id}`); })}><Button danger>Close</Button></Popconfirm></Space> }]} /></Card> },
      { key: 'people', label: 'People', children: <Card title="People" extra={<Space><Button type="primary" onClick={() => { personForm.resetFields(); setPerson(null); }}>Add person</Button><Button onClick={() => setLinkOpen(true)}>Add child to adult</Button></Space>}><Typography.Paragraph type="secondary">One person can have multiple roles. Child = learner; parent = guardian; tutor = instructor. Person details are study-independent.</Typography.Paragraph><Table rowKey="person_id" dataSource={people} pagination={{ pageSize: 8 }} columns={[{ title: 'Name', render: (_: unknown, r: Person) => String(r.profile.display_name || 'Unnamed') }, { title: 'Roles', dataIndex: 'roles', render: (rs: string[]) => rs.map(r => <Tag key={r}>{r}</Tag>) }, { title: 'Age', render: (_: unknown, r: Person) => String(r.profile.age || '—') }, { title: 'Email', render: (_: unknown, r: Person) => String(r.profile.email || '—') }, { title: 'Status', dataIndex: 'status' }, { title: 'Actions', render: (_: unknown, r: Person) => <Space><Button onClick={() => { setPerson(r); personForm.setFieldsValue({ ...r.profile, roles: r.roles }); }}>Edit</Button>{r.roles.includes('learner') && <><Button onClick={() => { linkForm.setFieldsValue({ learner: r.person_id }); setLinkOpen(true); }}>Link adult</Button><Button onClick={() => { setEnrollPerson(r); enrollForm.resetFields(); }}>Enroll</Button></>}<Popconfirm title="Deactivate this person?" onConfirm={() => void perform(async () => { await authRequest.delete(`/api/kiva/people/${r.person_id}`); })}><Button danger>Deactivate</Button></Popconfirm></Space> }]} /></Card> },
      { key: 'applications', label: 'Applications', children: <Card title="Applications" extra={<Button type="primary" onClick={() => { appForm.resetFields(); setAddApplicationOpen(true); }}>Add application</Button>}><Table rowKey="application_key" dataSource={applications} pagination={false} columns={[{ title: 'Name', dataIndex: 'name' }, { title: 'Key', dataIndex: 'application_key' }, { title: 'Status', dataIndex: 'status' }, { title: 'Actions', render: (_: unknown, row: Application) => <Space><Button onClick={() => { setApplication(row); appForm.setFieldsValue(row); }}>Edit</Button><Popconfirm title="Deactivate this application?" onConfirm={() => void perform(async () => { await authRequest.delete(`/api/kiva/applications/${row.application_key}`); })}><Button danger>Deactivate</Button></Popconfirm></Space> }]} /></Card> },
    ]} />
    <Modal open={person !== false} title={person ? 'Edit person' : 'Add person'} onCancel={() => setPerson(false)} onOk={savePerson} confirmLoading={busy}><Form autoComplete="off" form={personForm} layout="vertical"><Form.Item name="display_name" label="Name" rules={[{ required: true }]}><Input /></Form.Item><Form.Item name="roles" label="Roles" rules={[{ required: true }]}><Select mode="multiple" options={[{ label: 'Learner / child', value: 'learner' }, { label: 'Guardian / parent', value: 'guardian' }, { label: 'Instructor / tutor', value: 'instructor' }, { label: 'Tester', value: 'tester' }, { label: 'Developer', value: 'developer' }]} /></Form.Item><Form.Item name="age" label="Age (optional; usually for learners)"><Input type="number" /></Form.Item><Form.Item name="email" label="Email (optional; usually for adults)"><Input type="email" /></Form.Item></Form></Modal>
    <Modal open={!!study} title="Edit study" onCancel={() => setStudy(null)} onOk={saveStudy} confirmLoading={busy}><Form autoComplete="off" form={studyForm} layout="vertical"><Form.Item name="name" label="Name" rules={[{ required: true }]}><Input /></Form.Item><Form.Item name="status" label="Status"><Select options={['draft', 'active', 'closed'].map(value => ({ value }))} /></Form.Item></Form></Modal>
    <Modal open={!!application} title="Edit application" onCancel={() => setApplication(null)} onOk={saveApplication} confirmLoading={busy}><Form autoComplete="off" form={appForm} layout="vertical"><Form.Item name="name" label="Name" rules={[{ required: true }]}><Input /></Form.Item><Form.Item name="status" label="Status"><Select options={['active', 'inactive'].map(value => ({ value }))} /></Form.Item></Form></Modal>
    <Modal open={addApplicationOpen} title="Add application" onCancel={() => setAddApplicationOpen(false)} onOk={createApplication} confirmLoading={busy}><Form autoComplete="off" form={appForm} layout="vertical"><Form.Item name="application_key" label="Application key" rules={[{ required: true }]}><Input placeholder="e.g. reading_comprehension" /></Form.Item><Form.Item name="name" label="Display name" rules={[{ required: true }]}><Input placeholder="e.g. Reading comprehension" /></Form.Item></Form></Modal>
    <Modal open={linkOpen} title="Add child to adult" onCancel={() => setLinkOpen(false)} onOk={linkPeople} confirmLoading={busy}><Form autoComplete="off" form={linkForm} layout="vertical"><Form.Item name="guardian" label="Adult / guardian" rules={[{ required: true }]}><Select options={people.filter(p => p.status === 'active' && p.roles.includes('guardian')).map(p => ({ value: p.person_id, label: String(p.profile.display_name || p.person_id) }))} /></Form.Item><Form.Item name="learner" label="Child / learner" rules={[{ required: true }]}><Select options={people.filter(p => p.status === 'active' && p.roles.includes('learner')).map(p => ({ value: p.person_id, label: String(p.profile.display_name || p.person_id) }))} /></Form.Item></Form></Modal>
    <Modal open={!!enrollPerson} title="Enroll learner in a study" onCancel={() => setEnrollPerson(null)} onOk={enrollLearner} confirmLoading={busy}><Form autoComplete="off" form={enrollForm} layout="vertical"><Form.Item label="Learner"><Input value={String(enrollPerson?.profile.display_name || '')} disabled /></Form.Item><Form.Item name="study_id" label="Study" rules={[{ required: true }]}><Select options={studies.filter(s => s.status !== 'closed').map(s => ({ value: s.study_id, label: s.name }))} /></Form.Item></Form></Modal>
    <Modal open={!!addLearnerStudy} title={`Add a learner to ${addLearnerStudy?.name || ''}`} onCancel={() => setAddLearnerStudy(null)} onOk={addLearner} confirmLoading={busy} okText="Add learner"><Form autoComplete="off" form={learnerForm} layout="vertical" initialValues={{ mode: 'new' }}><Form.Item name="mode"><Radio.Group optionType="button" options={[{ label: 'New learner', value: 'new' }, { label: 'Existing learner', value: 'existing' }]} /></Form.Item><Form.Item noStyle shouldUpdate={(prev, cur) => prev.mode !== cur.mode}>{({ getFieldValue }) => getFieldValue('mode') === 'existing' ? <Form.Item name="learner_person_id" label="Learner" rules={[{ required: true, message: 'Pick a learner.' }]}><Select options={people.filter(p => p.status === 'active' && p.roles.includes('learner')).map(p => ({ value: p.person_id, label: String(p.profile.display_name || p.person_id) }))} /></Form.Item> : <><Form.Item name="display_name" label="Name" rules={[{ required: true, message: 'Enter a name.' }]}><Input placeholder="e.g. Student 2" /></Form.Item><Form.Item name="age" label="Age (optional)"><Input type="number" /></Form.Item></>}</Form.Item></Form></Modal>
  </>;
}
