// src/components/VersionBadge.tsx
// Small "V2.0.1" badge, fetched from /api/kiva/version. Must be used inside AuthProvider.
import { useEffect, useState } from 'react';
import { Tag } from 'antd';
import { useAuth } from '../contexts/AuthContext';

export default function VersionBadge() {
  const { authRequest } = useAuth();
  const [version, setVersion] = useState<string | null>(null);

  useEffect(() => {
    authRequest.get('/api/kiva/version').then(r => setVersion(r.data?.version || null)).catch(() => {});
  }, [authRequest]);

  if (!version) return null;
  // "v2.0.1" -> "V2.0.1"; leave commit-hash fallbacks (local dev) as-is.
  const label = /\d+\.\d+/.test(version) ? 'V' + version.replace(/^v/i, '') : version;
  return <Tag color="blue" style={{ fontWeight: 600, marginRight: 0 }}>{label}</Tag>;
}
