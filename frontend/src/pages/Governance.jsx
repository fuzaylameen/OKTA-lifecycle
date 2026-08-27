import { useState, useEffect } from 'react';
import { listAuthzLogs } from '../api/client';
import RotateMark from '../components/RotateMark';
import { Shield, Eye, ChevronDown, ChevronUp, RefreshCw } from 'lucide-react';
import './Governance.css';

// ── 7-Policy Engine Definitions (Directly matches backend app/authorization/policies.py) ───

const POLICIES = [
  {
    id: 'P1',
    name: 'PreventSelfDeprovisionPolicy',
    priority: 'CRITICAL',
    status: 'ACTIVE',
    category: 'Identity Protection',
    description: 'Prevents any user — including Admins — from deprovisioning their own account.',
    enforcement: 'Deny if requester.id == target.id AND action in [deprovision, delete, deactivate]',
  },
  {
    id: 'P2',
    name: 'ManagerCannotModifyAdminPolicy',
    priority: 'HIGH',
    status: 'ACTIVE',
    category: 'Privilege Separation',
    description: 'Prevents Managers from creating, deactivating, or modifying Admin-level accounts.',
    enforcement: 'Deny if requester.role == Manager AND target.role in [Admin, RoleManager]',
  },
  {
    id: 'P3',
    name: 'ManagerCannotDeprovisionManagerOrAdminPolicy',
    priority: 'HIGH',
    status: 'ACTIVE',
    category: 'Privilege Separation',
    description: 'Prevents a Manager from deprovisioning peers (Managers) or superiors (Admins).',
    enforcement: 'Deny if requester.role == Manager AND target.role in [Manager, Admin] AND action == deprovision',
  },
  {
    id: 'P4',
    name: 'SuspensionRequiresReasonPolicy',
    priority: 'MEDIUM',
    status: 'ACTIVE',
    category: 'Audit Compliance',
    description: 'All suspension requests must include a documented non-empty business justification.',
    enforcement: 'Deny if action == suspend AND (reason is NULL or empty)',
  },
  {
    id: 'P5',
    name: 'PreventPrivilegeEscalationPolicy',
    priority: 'CRITICAL',
    status: 'ACTIVE',
    category: 'Privilege Escalation',
    description: 'Prevents any role from assigning a privilege tier higher than their own authorization level.',
    enforcement: 'Deny if target.role.level > requester.role.level AND action == role_manage',
  },
  {
    id: 'P6',
    name: 'PreventSelfRoleEscalationPolicy',
    priority: 'CRITICAL',
    status: 'ACTIVE',
    category: 'Privilege Escalation',
    description: 'Prevents any identity from elevating their own role or privilege tier via self-assignment.',
    enforcement: 'Deny if requester.id == target.id AND action == role_manage',
  },
  {
    id: 'P7',
    name: 'PrivilegedUserProtectionPolicy',
    priority: 'HIGH',
    status: 'ACTIVE',
    category: 'Identity Protection',
    description: 'Requires RoleManager-level authorization for any lifecycle action targeting Admin accounts.',
    enforcement: 'Deny if target.role == Admin AND requester.role not in [Admin, RoleManager]',
  },
];

function formatDate(dateStr) {
  if (!dateStr) return '—';
  try {
    return new Intl.DateTimeFormat('en-US', {
      dateStyle: 'medium', timeStyle: 'short'
    }).format(new Date(dateStr));
  } catch {
    return dateStr;
  }
}

function PriorityBadge({ priority }) {
  const cls =
    priority === 'CRITICAL' ? 'badge-danger' :
    priority === 'HIGH'     ? 'badge-warning' : 'badge-muted';
  return <span className={`badge ${cls}`}>{priority}</span>;
}

function PolicyCard({ policy, isExpanded, onToggle, triggeredCount, passedCount }) {
  return (
    <div className={`card policy-engine-card ${isExpanded ? 'expanded' : ''}`}>
      <div className="policy-card-header" onClick={onToggle}>
        <div className="flex items-center gap-sm">
          <div className="policy-status-dot" />
          <code className="policy-name-code">{policy.name}</code>
        </div>
        <div className="flex items-center gap-sm">
          <PriorityBadge priority={policy.priority} />
          <span className="badge badge-muted">{policy.category}</span>
          {isExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </div>
      </div>

      {isExpanded && (
        <div className="policy-card-body">
          <p className="policy-desc">{policy.description}</p>

          <div className="policy-rule-box">
            <span className="policy-rule-label">Enforcement Rule</span>
            <code className="policy-rule-code">{policy.enforcement}</code>
          </div>

          <div className="policy-stats-row">
            <div className="policy-stat">
              <span className="policy-stat-val" style={{ color: 'var(--status-danger)' }}>{triggeredCount}</span>
              <span className="policy-stat-label">Violations Blocked</span>
            </div>
            <div className="policy-stat">
              <span className="policy-stat-val" style={{ color: 'var(--status-success)' }}>{passedCount}</span>
              <span className="policy-stat-label">Operations Allowed</span>
            </div>
            <div className="policy-stat">
              <span className="policy-stat-val" style={{ color: 'var(--mark-color-a)' }}>Active</span>
              <span className="policy-stat-label">Enforcement Status</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Governance() {
  const [expandedPolicy, setExpandedPolicy] = useState('P1');
  const [authzLogs, setAuthzLogs]           = useState([]);
  const [loading, setLoading]               = useState(true);
  const [error, setError]                   = useState('');

  const fetchAuthz = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await listAuthzLogs();
      setAuthzLogs(data || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAuthz();
  }, []);

  const totalDenied = authzLogs.filter((l) => l.decision?.toUpperCase() === 'DENIED').length;
  const totalAllowed = authzLogs.filter((l) => l.decision?.toUpperCase() === 'ALLOWED').length;

  return (
    <div className="governance-page">
      {/* Header */}
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="page-title">Policy Governance Engine</h1>
          <p className="page-subtitle">
            7-policy identity authorization matrix with real-time backend enforcement
          </p>
        </div>
        <div className="flex items-center gap-sm">
          <RotateMark size={28} isLoading={loading} />
          <button className="btn btn-secondary btn-sm" onClick={fetchAuthz} title="Refresh">
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {error && <div className="error-box" style={{ marginBottom: 20 }}>⚠ {error}</div>}

      {/* Metric Overview */}
      <div className="grid-4" style={{ marginBottom: 28 }}>
        <div className="metric-card">
          <span className="metric-label">Active Policies</span>
          <span className="metric-value" style={{ color: 'var(--mark-color-a)' }}>7</span>
          <span className="metric-sub">Real-time enforcement</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Critical Priority</span>
          <span className="metric-value" style={{ color: 'var(--status-danger)' }}>
            {POLICIES.filter((p) => p.priority === 'CRITICAL').length}
          </span>
          <span className="metric-sub">Privilege protection</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Violations Blocked</span>
          <span className="metric-value" style={{ color: 'var(--status-warning)' }}>
            {totalDenied}
          </span>
          <span className="metric-sub">Logged in authz audit</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Operations Authorized</span>
          <span className="metric-value" style={{ color: 'var(--status-success)' }}>
            {totalAllowed}
          </span>
          <span className="metric-sub">Policy checks passed</span>
        </div>
      </div>

      {/* Policy Matrix — Expandable Cards */}
      <div style={{ marginBottom: 28 }}>
        <div className="flex items-center gap-sm" style={{ marginBottom: 16 }}>
          <Shield size={18} color="var(--mark-color-a)" />
          <h2 className="section-title">Policy Engine Matrix</h2>
        </div>

        <div className="policy-matrix-list">
          {POLICIES.map((policy) => {
            const matchedLogs = authzLogs.filter((l) => l.policy_name?.toLowerCase().includes(policy.id.toLowerCase()) || l.policy_name?.toLowerCase().includes(policy.name.toLowerCase()));
            const trig = matchedLogs.filter((l) => l.decision?.toUpperCase() === 'DENIED').length;
            const pass = matchedLogs.filter((l) => l.decision?.toUpperCase() === 'ALLOWED').length;

            return (
              <PolicyCard
                key={policy.id}
                policy={policy}
                isExpanded={expandedPolicy === policy.id}
                onToggle={() => setExpandedPolicy((prev) => prev === policy.id ? null : policy.id)}
                triggeredCount={trig}
                passedCount={pass}
              />
            );
          })}
        </div>
      </div>

      {/* Live Policy Decisions Table connected to GET /api/logs/authz */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '18px 20px 16px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div className="flex items-center gap-sm">
            <Eye size={17} color="var(--mark-color-a)" />
            <h2 className="section-title">Live Security Decision Logs</h2>
          </div>
          <span className="badge badge-muted">{authzLogs.length} events recorded</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Requester ID</th>
              <th>Role</th>
              <th>Action</th>
              <th>Target ID</th>
              <th>Decision</th>
              <th>Policy</th>
              <th>Reason</th>
              <th>Timestamp</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 3 }, (_, i) => (
                <tr key={i}>
                  <td colSpan={8} style={{ padding: 16 }}>
                    <div className="skeleton" style={{ height: 16, width: '100%' }} />
                  </td>
                </tr>
              ))
            ) : authzLogs.length === 0 ? (
              <tr>
                <td colSpan={8} className="loading-row" style={{ color: 'var(--text-muted)' }}>
                  No security authorization decisions recorded yet.
                </td>
              </tr>
            ) : (
              authzLogs.map((d, idx) => (
                <tr
                  key={d.id || idx}
                  className="governance-row-animated"
                  style={{ '--row-delay': `${idx * 30}ms` }}
                >
                  <td className="font-mono" style={{ fontSize: 12.5 }}>{d.requester_id}</td>
                  <td><span className="badge badge-muted">{d.requester_role}</span></td>
                  <td><span className="font-bold" style={{ fontSize: 13 }}>{d.action}</span></td>
                  <td className="font-mono" style={{ fontSize: 12.5 }}>{d.target_id || '—'}</td>
                  <td>
                    <span className={`badge ${d.decision?.toUpperCase() === 'ALLOWED' ? 'badge-success' : 'badge-danger'}`}>
                      {d.decision}
                    </span>
                  </td>
                  <td>
                    {d.policy_name ? (
                      <code className="policy-chip" style={{ fontSize: 10.5 }}>{d.policy_name}</code>
                    ) : (
                      <span style={{ color: 'var(--text-muted)' }}>RBAC</span>
                    )}
                  </td>
                  <td style={{ fontSize: 12, color: 'var(--text-secondary)', maxWidth: 260 }}>
                    {d.reason || '—'}
                  </td>
                  <td style={{ fontSize: 11, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                    {formatDate(d.created_at)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default Governance;
