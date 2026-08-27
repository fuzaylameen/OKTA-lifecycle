import { useEffect, useState } from 'react';
import { listGroups, moveUser } from '../api/client';
import RotateMark from '../components/RotateMark';
import { Shield, Users, ArrowRight, RefreshCw, X } from 'lucide-react';
import './Groups.css';

// ── Real 4-Tier RBAC Model ────────────────────────────────────────────────────

const RBAC_TIERS = [
  {
    role: 'RoleManager',
    group: 'Identity-Role-Managers',
    level: 4,
    color: 'var(--mark-color-b)',
    badgeClass: 'badge-preview',
    description: 'Privilege assignment, policy governance, and cross-tier role management.',
    permissions: [
      'Assign roles to any tier',
      'Modify policy enforcement rules',
      'Governance audit access',
      'Full identity lifecycle control',
    ],
  },
  {
    role: 'Admin',
    group: 'Identity-Admins',
    level: 3,
    color: 'var(--mark-color-a)',
    badgeClass: 'badge-provisioned',
    description: 'Full lifecycle management, bulk operations, and audit log access.',
    permissions: [
      'Create, provision, deactivate users',
      'Bulk identity operations',
      'Force password expiry',
      'Full audit log access',
    ],
  },
  {
    role: 'Manager',
    group: 'Identity-Managers',
    level: 2,
    color: 'var(--status-success)',
    badgeClass: 'badge-active',
    description: 'Operational user provisioning and deprovisioning for managed teams.',
    permissions: [
      'Provision managed team members',
      'Deactivate non-admin users',
      'View audit events',
      'Submit role assignment requests',
    ],
  },
  {
    role: 'Auditor',
    group: 'Identity-Auditors',
    level: 1,
    color: 'var(--status-warning)',
    badgeClass: 'badge-muted',
    description: 'Read-only access to identity records, audit logs, and policy decisions.',
    permissions: [
      'Read user directory',
      'Read audit logs',
      'View policy governance matrix',
      'View RBAC tier assignments',
    ],
  },
];

// ── Move User Modal ───────────────────────────────────────────────────────────

function MoveUserModal({ groups, onClose, onMoved }) {
  const [userId, setUserId]       = useState('');
  const [oldGroupId, setOldGroupId] = useState('');
  const [newGroupId, setNewGroupId] = useState('');
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!userId || !oldGroupId || !newGroupId || oldGroupId === newGroupId) {
      setError('Please fill in all fields and select different source/target groups.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await moveUser(userId, oldGroupId, newGroupId);
      onMoved();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">Move Identity Between Groups</h3>
          <button className="btn-icon" onClick={onClose}><X size={16} /></button>
        </div>

        {error && <div className="error-box" style={{ marginBottom: 16 }}>{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Okta User ID *</label>
            <input
              required
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="00u1abc2defG3HIjK"
            />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 12, alignItems: 'center' }}>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">From Group *</label>
              <select required value={oldGroupId} onChange={(e) => setOldGroupId(e.target.value)}>
                <option value="">Select source group…</option>
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>{g.profile?.name || g.id}</option>
                ))}
              </select>
            </div>
            <ArrowRight size={18} color="var(--text-muted)" style={{ marginTop: 16 }} />
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">To Group *</label>
              <select required value={newGroupId} onChange={(e) => setNewGroupId(e.target.value)}>
                <option value="">Select target group…</option>
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>{g.profile?.name || g.id}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Processing…' : 'Move User'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Main Groups Component ─────────────────────────────────────────────────────

function Groups() {
  const [groups, setGroups]       = useState([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState('');
  const [showMove, setShowMove]   = useState(false);

  const fetchGroups = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await listGroups();
      setGroups(data || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchGroups(); }, []);

  return (
    <div className="groups-page">
      {/* Header */}
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="page-title">Access & Groups</h1>
          <p className="page-subtitle">
            4-tier RBAC privilege model — Okta group to role mapping
          </p>
        </div>
        <div className="flex items-center gap-sm">
          <RotateMark size={28} isLoading={loading} />
          <button className="btn btn-secondary btn-sm" onClick={fetchGroups}>
            <RefreshCw size={14} />
          </button>
          <button className="btn btn-primary btn-sm" onClick={() => setShowMove(true)}>
            <ArrowRight size={14} /> Move User
          </button>
        </div>
      </div>

      {/* 4-Tier RBAC Privilege Cards */}
      <div className="rbac-tiers-grid" style={{ marginBottom: 32 }}>
        {RBAC_TIERS.map((tier) => (
          <div
            key={tier.role}
            className="card rbac-tier-card"
            style={{ '--tier-color': tier.color }}
          >
            <div className="tier-header">
              <div className="tier-icon" style={{ background: `${tier.color}18`, border: `1px solid ${tier.color}30` }}>
                <Shield size={18} color={tier.color} />
              </div>
              <div>
                <div className="flex items-center gap-sm" style={{ marginBottom: 2 }}>
                  <span className={`badge ${tier.badgeClass}`}>{tier.role}</span>
                  <span className="tier-level-badge">Level {tier.level}</span>
                </div>
                <code className="tier-group-name">{tier.group}</code>
              </div>
            </div>

            <p className="tier-description">{tier.description}</p>

            <div className="tier-permissions">
              {tier.permissions.map((perm) => (
                <div key={perm} className="tier-perm-row">
                  <div className="perm-dot" style={{ background: tier.color }} />
                  <span>{perm}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Live Okta Groups Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '18px 20px 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div className="flex items-center gap-sm">
            <Users size={18} color="var(--mark-color-a)" />
            <h2 className="section-title">Live Okta Groups</h2>
          </div>
          <span className="badge badge-muted">{loading ? '…' : groups.length} groups</span>
        </div>

        {error && <div className="error-box" style={{ margin: 16 }}>⚠ {error}</div>}

        <table>
          <thead>
            <tr>
              <th>Group Name</th>
              <th>Group ID</th>
              <th>RBAC Role Mapping</th>
              <th>Privilege Level</th>
              <th>Member Count</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 4 }, (_, i) => (
                <tr key={i} className="skeleton-row">
                  {Array.from({ length: 5 }, (_, j) => (
                    <td key={j} style={{ padding: '14px 16px' }}>
                      <div className="skeleton" style={{ height: 14, borderRadius: 4, width: '70%' }} />
                    </td>
                  ))}
                </tr>
              ))
            ) : groups.length === 0 ? (
              <tr>
                <td colSpan={5} className="loading-row" style={{ color: 'var(--text-muted)' }}>
                  No Okta groups found. Verify backend connection.
                </td>
              </tr>
            ) : (
              groups.map((g, idx) => {
                const name = g.profile?.name || g.id || 'Unknown';
                const tier = RBAC_TIERS.find((t) =>
                  name.toLowerCase().includes(t.role.toLowerCase()) ||
                  name.toLowerCase().includes(t.group.toLowerCase())
                );
                return (
                  <tr
                    key={g.id}
                    className="group-row-animated"
                    style={{ '--row-delay': `${Math.min(idx * 30, 200)}ms` }}
                  >
                    <td>
                      <span className="font-bold" style={{ fontSize: 14, color: 'var(--text-primary)' }}>
                        {name}
                      </span>
                    </td>
                    <td>
                      <code className="font-mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        {g.id}
                      </code>
                    </td>
                    <td>
                      {tier ? (
                        <span className={`badge ${tier.badgeClass}`}>{tier.role}</span>
                      ) : (
                        <span className="badge badge-muted">Unmapped</span>
                      )}
                    </td>
                    <td>
                      {tier ? (
                        <span className="font-bold" style={{ color: tier.color }}>
                          Level {tier.level}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>—</span>
                      )}
                    </td>
                    <td style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
                      {g.objectClass?.[0] || 'Okta Group'}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Move User Modal */}
      {showMove && (
        <MoveUserModal
          groups={groups}
          onClose={() => setShowMove(false)}
          onMoved={fetchGroups}
        />
      )}
    </div>
  );
}

export default Groups;
