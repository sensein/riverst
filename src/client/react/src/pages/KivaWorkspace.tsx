import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Button, Card, Checkbox, Empty, Form, Input, Modal, Select, Space, Spin, Tag, Tabs, Typography } from 'antd';
import { BookOutlined } from '@ant-design/icons';
import { useAuth } from '../contexts/AuthContext';
import KivaAdmin from './KivaAdmin';
import KivaProblems from './KivaProblems';

type App = { application_key: string; name: string; enabled: boolean };
type Study = { study_id: string; name: string; applications: App[] };
type Subject = { person: { person_id: string; profile: Record<string, unknown>; roles: string[] }; studies: Study[] };
type Menu = { actor: { roles: string[] }; subjects: Subject[] };

const apps = {
  listen_audiobooks: { name: 'Listen to audiobooks', config: { route: '/listen-to-an-audio-book' } },
  vocabulary: {
    name: 'Learning vocabulary',
    config: {
      name: 'vocab-tutoring',
      description: 'Vocab Tutoring',
      advanced_flows: true,
      advanced_flows_config_path: './activities/vocab-tutoring/flow_config.json',
      activity_variables_path: './activities/vocab-tutoring/resources/the_tale_of_peter_rabbit.json',
      index: 1,
      vocab_override: [],
      prolific_campaign: false,
      pipeline_modality: 'classic',
      stt_type: 'openai',
      llm_type: 'openai',
      tts_type: 'openai',
      tts_voice: 'alloy',
      tts_model: 'tts-1',
      embodiment: 'humanoid_avatar',
      body_animations: ['dance', 'wave', 'i_have_a_question', 'thank_you', 'i_dont_know', 'ok', 'thumbup', 'thumbdown', 'happy', 'sad', 'angry', 'fear', 'disgust', 'love', 'sleep', 'thinking'],
      camera_settings: 'upper',
      user_description: 'The learner is practicing vocabulary from their first reading lesson.',
      short_term_memory: false,
      long_term_memory: false,
      languages: ['english'],
      video_flag: false,
      video_out_width: 640,
      video_out_height: 320,
      video_out_framerate: 30,
      user_transcript: true,
      bot_transcript: true,
    },
  },
};

export default function KivaWorkspace() {
  const { authRequest, isAuthenticated, isLoading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [menu, setMenu] = useState<Menu | null>(null);
  const [subject, setSubject] = useState<Subject | null>(null);
  const [study, setStudy] = useState<Study | null>(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const [newStudy, setNewStudy] = useState(false);
  const [section, setSection] = useState('workspace');
  const [studyForm] = Form.useForm();

  const refresh = async () => {
    setLoading(true);
    try {
      const result = await authRequest.get('/api/kiva/menu');
      const data = result.data as Menu;
      setMenu(data);
      const first = data.subjects[0];
      if (first) { setSubject(first); setStudy(first.studies[0] ?? null); }
    } catch (caught: any) { setError(caught.response?.data?.detail || 'Could not load KIVA.'); }
    finally { setLoading(false); }
  };
  useEffect(() => {
    if (!authLoading && isAuthenticated) void refresh();
  }, [authLoading, isAuthenticated]);
  const perform = async (action: () => Promise<void>) => {
    setWorking(true); setError('');
    try { await action(); } catch (caught: any) { setError(caught.response?.data?.detail || caught.message || 'This action could not be completed.'); }
    finally { setWorking(false); }
  };
  const createStudy = () => perform(async () => {
    const values = await studyForm.validateFields();
    const keys: string[] = values.applications;
    const created = await authRequest.post('/api/kiva/studies', { name: values.name, definition: { intake: { learner: [], guardian: [] }, applications: keys } });
    await authRequest.patch(`/api/kiva/studies/${created.data.study_id}`, { status: 'active' });
    await Promise.all(keys.map(async key => {
      const app = apps[key as keyof typeof apps];
      await authRequest.post('/api/kiva/applications', { application_key: key, name: app.name });
      await authRequest.post(`/api/kiva/studies/${created.data.study_id}/applications`, { application_key: key, config: app.config, enabled: true });
    }));
    setStudy({ ...created.data, applications: keys.map(key => ({ application_key: key, name: apps[key as keyof typeof apps].name, enabled: true })) });
    studyForm.resetFields(); setNewStudy(false); await refresh();
    window.dispatchEvent(new Event('kiva:refresh-admin'));
  });
  const unlockBrowserAudio = async () => {
    const AudioContextType = window.AudioContext;
    if (!AudioContextType) return;
    const context = new AudioContextType();
    try { await context.resume(); }
    finally { await context.close(); }
  };

  const launch = (applicationKey: string) => perform(async () => {
    // Preserve the launch button's user gesture so browser audio playback is
    // unlocked before the asynchronous session setup and navigation.
    await unlockBrowserAudio();
    if (!subject || !study) throw new Error('Select an enrolled learner and study first.');
    if (applicationKey === 'listen_audiobooks') { navigate('/listen-to-an-audio-book'); return; }
    const payload: Record<string, unknown> = {};
    if (applicationKey === 'vocabulary') {
      const avatarResponse = await authRequest.get('/api/avatars');
      const avatars = avatarResponse.data as Array<{ id?: number }>;
      const avatar = avatars.find(item => item.id === 4) ?? avatars[0];
      if (!avatar) throw new Error('No avatar is available for the vocabulary lesson.');
      payload.avatar = avatar;
    }
    const result = await authRequest.post('/api/kiva/sessions', { subject_person_id: subject.person.person_id, study_id: study.study_id, application_key: applicationKey, metadata: payload });
    navigate(`/avatar-interaction/${result.data.session_id}`);
  });
  if (loading) return <div style={{ padding: 64, textAlign: 'center' }}><Spin size="large" /></div>;
  const instructor = menu?.actor?.roles?.includes('instructor');
  return <div style={{ maxWidth: 1120, margin: '0 auto', padding: '40px 24px', background: '#f5f7fb', minHeight: '100vh' }}>
    <Typography.Text type="secondary" style={{ letterSpacing: 1 }}>MIT KIVA TEAM</Typography.Text><Typography.Title level={1} style={{ marginTop: 4 }}>Learning, made personal.</Typography.Title><Typography.Paragraph type="secondary">Choose who is learning, then launch an activity from their enrolled study.</Typography.Paragraph>
    {error && <Alert message={error} type="error" closable onClose={() => setError('')} style={{ marginBottom: 16 }} />}
    <Tabs activeKey={section} onChange={setSection} items={[
      { key: 'workspace', label: 'Learning workspace', children: <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px,.8fr) minmax(380px,1.2fr)', gap: 20 }}>
        <Card title="Who is learning today?">{!menu?.subjects.length ? <Empty description={instructor ? 'Create a study, then add a parent and child.' : 'No enrolled learners yet'} /> : <Select style={{ width: '100%' }} value={subject?.person.person_id} onChange={id => { const selected = menu.subjects.find(item => item.person.person_id === id) ?? null; setSubject(selected); setStudy(selected?.studies[0] ?? null); }} options={menu.subjects.map(item => ({ value: item.person.person_id, label: String(item.person.profile.display_name || item.person.person_id) }))} />}{subject && <div style={{ marginTop: 20, padding: 16, borderRadius: 12, background: '#eef4ff' }}><b>{String(subject.person.profile.display_name || 'Learner')}</b><br /><Typography.Text type="secondary">{subject.person.roles.join(' · ')}</Typography.Text></div>}</Card>
        <Card title="Choose an activity" extra={study && <Tag color="blue">{study.name}</Tag>}>{!study ? <Empty description="Select an enrolled learner and study" /> : <Space direction="vertical" size={14} style={{ width: '100%' }}>{study.applications.filter(app => app.enabled).map(app => <Card key={app.application_key} size="small"><Space><BookOutlined style={{ fontSize: 22, color: '#2656d8' }} /><div><b>{app.name}</b><br /><Typography.Text type="secondary">Available through this study</Typography.Text></div><Button type="primary" loading={working} onClick={() => launch(app.application_key)}>Start</Button></Space></Card>)}</Space>}</Card>
      </div> },
      ...(instructor ? [{ key: 'manage', label: 'Manage studies, people & apps', children: <KivaAdmin onCreateStudy={() => setNewStudy(true)} /> }] : []),
      { key: 'testing', label: 'Testing & problems', children: <KivaProblems /> },
    ]} />
    <Modal open={newStudy} title="Create a study" onCancel={() => setNewStudy(false)} onOk={createStudy} confirmLoading={working} okText="Create study"><Form autoComplete="off" form={studyForm} layout="vertical" initialValues={{ applications: ['listen_audiobooks', 'vocabulary'] }}><Form.Item name="name" label="Study name" rules={[{ required: true, message: 'Enter a study name.' }]}><Input placeholder="e.g. Spring Reading Study" /></Form.Item><Form.Item name="applications" label="Applications"><Checkbox.Group options={[{ label: 'Listen to audiobooks', value: 'listen_audiobooks' }, { label: 'Learning vocabulary', value: 'vocabulary' }]} /></Form.Item></Form></Modal>
  </div>;
}
