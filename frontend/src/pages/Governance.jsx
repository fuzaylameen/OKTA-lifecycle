import { useState } from 'react';
import RotateMark from '../components/RotateMark';
import { Shield, Eye, ChevronDown, ChevronUp } from 'lucide-react';
import './Governance.css';

// ── 7-Policy Engine Definitions ───────────────────────────────────────────────

const POLICIES = [
  {
    id: 'P1',
    name: 'PreventSelfDeprovisionPolicy',
    priority: 'CRITICAL',
    status: 'ACTIVE',
    category: 'Identity Protection',
    description: 'Prevents any user — including Admins — from deprovisioning their own account.',
    enforcement: 'Deny if requester.id == target.id AND action == DEPROVISION',
    triggered: 3,
    passed: 287,
  },
  {
    id: 'P2',
    name: 'ManagerCannotModifyAdminPolicy',
    priority: 'HIGH',
    status: 'ACTIVE',
    category: 'Privilege Separation',
    description: 'Prevents Managers from creating, deactivating, or modifying Admin-level accounts.',
    enforcement: 'Deny if requester.role == Manager AND target.role == Admin',
    triggered: 7,
    passed: 241,
  },
  {
    id: 'P3',
    name: 'ManagerCannotDeprovisionManagerOrAdminPolicy',
    priority: 'HIGH',
    status: 'ACTIVE',
    category: 'Privilege Separation',
    description: 'Prevents a Manager from deprovisioning peers (Managers) or superiors (Admins).',
    enforcement: 'Deny if requester.role == Manager AND target.role IN [Manager, Admin] AND action == DEPROVISION',
    triggered: 4,
    passed: 195,
  },
  {
    id: 'P4',
    name: 'SuspensionRequiresReasonPolicy',
    priority: 'MEDIUM',
    status: 'ACTIVE',
    category: 'Audit Compliance',
    description: 'All suspension and deactivation requests must include a documented business justification.',
    enforcement: 'Deny if action == SUSPEND AND reason == NULL',
    triggered: 2,
    passed: 108,
  },
  {
    id: 'P5',
    name: 'PreventPrivilegeEscalationPolicy',
    priority: 'CRITICAL',
    status: 'ACTIVE',
    category: 'Privilege Escalation',
    description: 'Prevents any role from assigning a privilege tier higher than their own authorization level.',
    enforcement: 'Deny if target.role.level > requester.role.level AND action == ASSIGN_ROLE',
    triggered: 11,
    passed: 310,
  },
  {
    id: 'P6',
    name: 'PreventSelfRoleEscalationPolicy',
    priority: 'CRITICAL',
    status: 'ACTIVE',
    category: 'Privilege Escalation',
    description: 'Prevents any identity from elevating their own role or privilege tier via self-assignment.',
    enforcement: 'Deny if requester.id == target.id AND action == ASSIGN_ROLE',
    triggered: 5,
    passed: 188,
  },
  {
    id: 'P7',
    name: 'PrivilegedUserProtectionPolicy',
    priority: 'HIGH',
    status: 'ACTIVE',
    category: 'Identity Protection',
    description: 'Requires RoleManager-level authorization for any lifecycle action targeting Admin accounts.',
    enforcement: 'Deny if target.role == Admin AND requester.role != [Admin, RoleManager]',
    triggered: 6,
    passed: 217,
  },
];

// Recent policy decisions sourced from audit + policy logs
const RECENT_DECISIONS = [
  {
    requester: 'sarah.manager@corp.com',
    role: 'Manager',
    action: 'MODIFY_ADMIN_ACCOUNT',
    target: 'super.admin@corp.com',
    decision: 'DENIED',
    policy: 'ManagerCannotModifyAdminPolicy',
    reason: 'Manager-tier identity lacks authorization to modify Admin-level accounts.',
    ts: '5 minutes ago',
  },
  {
    requester: 'alex.admin@corp.com',
    role: 'Admin',
    action: 'SELF_DEPROVISION',
    target: 'alex.admin@corp.com',
    decision: 'DENIED',
    policy: 'PreventSelfDeprovisionPolicy',
    reason: 'Self-deprovision is categorically blocked by identity protection policy.',
    ts: '24 minutes ago',
  },
  {
    requester: 'governance.lead@corp.com',
    role: 'RoleManager',
    action: 'ASSIGN_ROLE_TIER',
    target: 'auditor.lead@corp.com',
    decision: 'ALLOWED',
    policy: 'PreventPrivilegeEscalationPolicy',
    reason: 'RoleManager (Level 4) has authorization to assign Auditor (Level 1) tier.',
    ts: '3 hours ago',
  },
  {
    requester: 'team.manager@corp.com',
    role: 'Manager',
    action: 'ASSIGN_ROLE_TIER',
    target: 'contractor@corp.com',
    decision: 'DENIED',
    policy: 'PreventPrivilegeEscalationPolicy',
    reason: 'Requested role tier exceeds requester authorization level.',
    ts: '5 hours ago',
  },
];

function PriorityBadge({ priority }) {
  const cls =
    priority === 'CRITICAL' ? 'badge-danger' :
    priority === 'HIGH'     ? 'badge-warning' : 'badge-muted';
  return <span className={`badge ${cls}`}>{priority}</span>;
}

function PolicyCard({ policy, isExpanded, onToggle }) {
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
              <span className="policy-stat-val" style={{ color: 'var(--status-danger)' }}>{policy.triggered}</span>
              <span className="policy-stat-label">Violations Blocked</span>
            </div>
            <div className="policy-stat">
              <span className="policy-stat-val" style={{ color: 'var(--status-success)' }}>{policy.passed}</span>
              <span className="policy-stat-label">Operations Passed</span>
            </div>
            <div className="policy-stat">
              <span className="policy-stat-val" style={{ color: 'var(--mark-color-a)' }}>
                {((policy.passed / (policy.passed + policy.triggered)) * 100).toFixed(1)}%
              </span>
              <span className="policy-stat-label">Pass Rate</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Governance() {
  const [expandedPolicy, setExpandedPolicy] = useState('P1');

  return (
    <div className="governance-page">
      {/* Header */}
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="page-title">Policy Governance Engine</h1>
          <p className="page-subtitle">
            7-policy identity authorization matrix with real-time enforcement monitoring
          </p>
        </div>
        <div className="flex items-center gap-sm">
          <RotateMark size={28} />
          <div className="flex items-center gap-sm">
            <span className="status-pulse-dot" />
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--status-success)' }}>
              All 7 Policies Active
            </span>
          </div>
        </div>
      </div>

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
          <span className="metric-label">Violations Blocked (All Time)</span>
          <span className="metric-value" style={{ color: 'var(--status-warning)' }}>
            {POLICIES.reduce((s, p) => s + p.triggered, 0)}
          </span>
          <span className="metric-sub">Denied by policy engine</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Operations Authorized</span>
          <span className="metric-value" style={{ color: 'var(--status-success)' }}>
            {POLICIES.reduce((s, p) => s + p.passed, 0)}
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
          {POLICIES.map((policy) => (
            <PolicyCard
              key={policy.id}
              policy={policy}
              isExpanded={expandedPolicy === policy.id}
              onToggle={() => setExpandedPolicy((prev) => prev === policy.id ? null : policy.id)}
            />
          ))}
        </div>
      </div>

      {/* Recent Policy Decisions Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '18px 20px 16px', borderBottom: '1px solid var(--border-subtle)' }}>
          <div className="flex items-center gap-sm">
            <Eye size={17} color="var(--mark-color-a)" />
            <h2 className="section-title">Recent Policy Decisions</h2>
          </div>
        </div>
        <table>
          <thead>
            <tr>
              <th>Requester</th>
              <th>Role</th>
              <th>Action</th>
              <th>Target</th>
              <th>Decision</th>
              <th>Applied Policy</th>
              <th>Enforcement Reason</th>
              <th>When</th>
            </tr>
          </thead>
          <tbody>
            {RECENT_DECISIONS.map((d, idx) => (
              <tr
                key={idx}
                className="governance-row-animated"
                style={{ '--row-delay': `${idx * 40}ms` }}
              >
                <td className="font-mono" style={{ fontSize: 12.5 }}>{d.requester}</td>
                <td><span className="badge badge-muted">{d.role}</span></td>
                <td><span className="font-bold" style={{ fontSize: 13 }}>{d.action}</span></td>
                <td className="font-mono" style={{ fontSize: 12.5 }}>{d.target}</td>
                <td>
                  <span className={`badge ${d.decision === 'ALLOWED' ? 'badge-success' : 'badge-danger'}`}>
                    {d.decision}
                  </span>
                </td>
                <td>
                  <code className="policy-chip" style={{ fontSize: 10.5 }}>{d.policy}</code>
                </td>
                <td style={{ fontSize: 12, color: 'var(--text-secondary)', maxWidth: 260 }}>
                  {d.reason}
                </td>
                <td style={{ fontSize: 11, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                  {d.ts}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default Governance;
