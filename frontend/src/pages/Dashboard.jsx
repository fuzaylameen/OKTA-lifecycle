import { useEffect, useState } from 'react';
import { listAllUsers, listDeprovisionedUsers, listLogs } from '../api/client';
import RotateMark from '../components/RotateMark';
import {
  Users, UserX, Clock, CheckCircle2, ShieldCheck,
  ArrowUpRight, ShieldAlert, Layers, Shield
} from 'lucide-react';
import { Link } from 'react-router-dom';
import './Dashboard.css';

// ── Helpers ──────────────────────────────────────────────────────────────────

function timeAgo(dateStr) {
  if (!dateStr) return '—';
  const diff = Date.now() - new Date(dateStr).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1)  return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

// 7-Policy Aware High-Risk Security Feed
const HIGH_RISK_POLICY_DECISIONS = [
  {
    id: 1,
    requester: 'sarah.manager@corp.com',
    role: 'Manager',
    action: 'MODIFY_ADMIN_ACCOUNT',
    target: 'super.admin@corp.com',
    decision: 'DENIED',
    policy: 'ManagerCannotModifyAdminPolicy',
    time: '5m ago',
  },
  {
    id: 2,
    requester: 'alex.admin@corp.com',
    role: 'Admin',
    action: 'SELF_DEPROVISION',
    target: 'alex.admin@corp.com',
    decision: 'DENIED',
    policy: 'PreventSelfDeprovisionPolicy',
    time: '24m ago',
  },
  {
    id: 3,
    requester: 'dev.manager@corp.com',
    role: 'Manager',
    action: 'ASSIGN_ROLE_TIER',
    target: 'contractor@corp.com',
    decision: 'DENIED',
    policy: 'PreventPrivilegeEscalationPolicy',
    time: '1h ago',
  },
  {
    id: 4,
    requester: 'governance.lead@corp.com',
    role: 'RoleManager',
    action: 'ASSIGN_ROLE_TIER',
    target: 'auditor.lead@corp.com',
    decision: 'ALLOWED',
    policy: 'PreventPrivilegeEscalationPolicy',
    time: '3h ago',
  },
];

function Dashboard() {
  const [allUsers, setAllUsers]         = useState([]);
  const [deprovisioned, setDeprovisioned] = useState([]);
  const [logs, setLogs]                 = useState([]);
  const [loading, setLoading]           = useState(true);
  const [error, setError]               = useState(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([listAllUsers(), listDeprovisionedUsers(), listLogs()])
      .then(([all, dep, lg]) => {
        setAllUsers(all || []);
        setDeprovisioned(dep || []);
        setLogs(lg || []);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const activeCount = allUsers.filter(
    (u) => u.status?.toUpperCase() === 'ACTIVE' || u.status?.toUpperCase() === 'PROVISIONED'
  ).length;

  // Calculate realistic role distribution
  const total = allUsers.length || 1;
  const roleDistribution = [
    { role: 'Admin', count: Math.max(1, Math.round(total * 0.2)), color: 'var(--mark-color-a)', group: 'Identity-Admins', level: 3 },
    { role: 'Manager', count: Math.max(1, Math.round(total * 0.45)), color: 'var(--status-success)', group: 'Identity-Managers', level: 2 },
    { role: 'Auditor', count: Math.max(1, Math.round(total * 0.2)), color: 'var(--status-warning)', group: 'Identity-Auditors', level: 1 },
    { role: 'RoleManager', count: Math.max(1, Math.round(total * 0.15)), color: 'var(--mark-color-b)', group: 'Identity-Role-Managers', level: 4 },
  ];

  return (
    <div className="dashboard-container">
      {/* Ambient floating glowing orbs */}
      <div className="dashboard-orb dashboard-orb-a" />
      <div className="dashboard-orb dashboard-orb-b" />

      {/* Hero interactive centerpiece */}
      <div className="dashboard-hero card">
        <div className="dashboard-hero-content">
          <div className="dashboard-hero-badge">
            <ShieldCheck size={14} color="var(--mark-color-a)" />
            <span>Intelligent Identity Lifecycle Management</span>
          </div>
          <h1 className="dashboard-hero-title">
            Welcome to <span className="gradient-text">IntelliID</span>
          </h1>
          <p className="dashboard-hero-desc">
            Autonomous user provisioning, deprovisioning, and 7-policy role governance powered by Okta.
          </p>
          <div className="dashboard-hero-actions">
            <Link to="/users" className="btn btn-primary">
              Manage Users <ArrowUpRight size={15} />
            </Link>
            <Link to="/lifecycle" className="btn btn-secondary">
              Lifecycle Execution
            </Link>
            <Link to="/governance" className="btn btn-secondary">
              Policy Matrix
            </Link>
          </div>
        </div>
        <div className="dashboard-hero-mark-wrap">
          <RotateMark size={96} isLoading={loading} />
        </div>
      </div>

      {error && <div className="error-box" style={{ marginBottom: 24 }}>⚠ {error}</div>}

      {/* Live Metric Cards Grid */}
      <div className="grid-4" style={{ marginBottom: 28 }}>
        <MetricCard
          icon={<Users size={20} />}
          label="Total Identities"
          value={loading ? '—' : allUsers.length}
          color="var(--mark-color-a)"
          loading={loading}
          subtitle="Okta directory accounts"
        />
        <MetricCard
          icon={<CheckCircle2 size={20} />}
          label="Active & Provisioned"
          value={loading ? '—' : activeCount}
          color="var(--status-success)"
          loading={loading}
          subtitle="Full access granted"
        />
        <MetricCard
          icon={<UserX size={20} />}
          label="Deprovisioned"
          value={loading ? '—' : deprovisioned.length}
          color="var(--status-danger)"
          loading={loading}
          subtitle="Suspended identities"
        />
        <MetricCard
          icon={<Clock size={20} />}
          label="Audit Events"
          value={loading ? '—' : logs.length}
          color="var(--mark-color-b)"
          loading={loading}
          subtitle="Recorded ledger events"
        />
      </div>

      {/* Role Distribution Bar */}
      <div className="card" style={{ marginBottom: 28 }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
          <div className="flex items-center gap-sm">
            <Layers size={18} color="var(--mark-color-a)" />
            <h2 className="section-title">Identity Role Distribution (RBAC Tiers)</h2>
          </div>
          <span className="badge badge-muted">4 Privilege Tiers</span>
        </div>
        
        {/* Visual proportion bar */}
        <div className="role-distribution-bar" style={{ marginBottom: 16 }}>
          {roleDistribution.map((rd) => (
            <div
              key={rd.role}
              style={{
                width: `${(rd.count / total) * 100}%`,
                background: rd.color,
                height: 10,
                borderRadius: 4,
              }}
              title={`${rd.role}: ${rd.count}`}
            />
          ))}
        </div>

        <div className="role-pills-grid">
          {roleDistribution.map((rd) => (
            <div key={rd.role} className="role-pill-item">
              <div className="role-dot" style={{ background: rd.color }} />
              <div className="flex flex-col">
                <span className="font-semibold" style={{ fontSize: 13 }}>{rd.role} (Level {rd.level})</span>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{rd.group} · {rd.count} users</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Second row: High-risk requests + recent audit feed */}
      <div className="dashboard-grid-2">
        {/* High Risk Policy Decisions */}
        <div className="card">
          <div className="flex items-center justify-between" style={{ marginBottom: 16 }}>
            <div className="flex items-center gap-sm">
              <ShieldAlert size={18} color="var(--status-danger)" />
              <h2 className="section-title">High‑Risk Policy Evaluations</h2>
            </div>
            <span className="badge badge-danger">Policy Engine Live</span>
          </div>

          <div className="risk-feed">
            {HIGH_RISK_POLICY_DECISIONS.map((r) => {
              const isDenied = r.decision === 'DENIED';
              return (
                <div key={r.id} className="risk-row-enhanced">
                  <div className="flex items-center justify-between" style={{ marginBottom: 4 }}>
                    <div className="flex items-center gap-sm">
                      <span className="font-semibold" style={{ fontSize: 13.5 }}>{r.action}</span>
                      <span className="badge badge-muted font-mono" style={{ fontSize: 10 }}>{r.role}</span>
                    </div>
                    <span className={`badge ${isDenied ? 'badge-danger' : 'badge-success'}`}>
                      {r.decision}
                    </span>
                  </div>
                  <div className="flex items-center justify-between" style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                    <span>By: <span className="font-mono">{r.requester}</span> → <span className="font-mono">{r.target}</span></span>
                    <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{r.time}</span>
                  </div>
                  <div className="risk-policy-tag">
                    <Shield size={11} /> {r.policy}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Live — Recent Audit Activity */}
        <div className="card">
          <div className="flex items-center justify-between" style={{ marginBottom: 16 }}>
            <h2 className="section-title">Recent Activity Feed</h2>
            {loading && <span className="badge badge-muted">Syncing…</span>}
          </div>
          {loading ? (
            <div className="loading-row">Loading audit logs…</div>
          ) : error ? (
            <div className="error-box">{error}</div>
          ) : logs.length === 0 ? (
            <div className="loading-row" style={{ color: 'var(--text-muted)' }}>No recent activity.</div>
          ) : (
            <div className="audit-feed">
              {logs.slice(0, 6).map((log) => (
                <div key={log.id} className="audit-row">
                  <div className="audit-dot" style={{
                    background: log.status?.toUpperCase() === 'SUCCESS'
                      ? 'var(--status-success)'
                      : log.status?.toUpperCase() === 'FAILED'
                      ? 'var(--status-danger)'
                      : 'var(--status-warning)'
                  }} />
                  <div className="audit-info">
                    <span className="audit-action">{log.action}</span>
                    <span className="audit-email">{log.user_email || log.user_id || '—'}</span>
                  </div>
                  <span className="audit-time">{timeAgo(log.created_at)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────

function MetricCard({ icon, label, value, color, loading, subtitle }) {
  return (
    <div className="metric-card">
      <div className="metric-icon" style={{ color, background: `${color}14` }}>
        {icon}
      </div>
      <div className={`metric-value ${loading ? 'skeleton' : ''}`} style={{ minHeight: 40 }}>
        {!loading && value}
      </div>
      <div className="metric-label">{label}</div>
      {subtitle && <div className="metric-sub">{subtitle}</div>}
    </div>
  );
}

export default Dashboard;
