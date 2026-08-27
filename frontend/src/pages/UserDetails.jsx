import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  getUserById, getUserPasswordExpiry, expireUserPassword,
  provisionUser, deactivateUser, deleteUser, getUserTimeline, listGroups
} from '../api/client';
import RotateMark from '../components/RotateMark';
import PolicyViolationModal from '../components/PolicyViolationModal';
import {
  ArrowLeft, Shield, User, Key, Clock, Zap, UserMinus,
  Trash2, Lock, AlertCircle, CheckCircle2, RefreshCw,
  Calendar, Layers, Check, ChevronRight
} from 'lucide-react';
import './UserDetails.css';

// ── Role & Group Mapping Matrix ───────────────────────────────────────────────

const ROLE_DEFINITIONS = {
  Admin: {
    group: 'Identity-Admins',
    level: 3,
    badgeClass: 'badge-provisioned',
    permissions: ['users:create', 'users:provision', 'users:deactivate', 'users:delete', 'audit:read', 'password:expire']
  },
  Manager: {
    group: 'Identity-Managers',
    level: 2,
    badgeClass: 'badge-active',
    permissions: ['users:provision', 'users:deactivate', 'audit:read']
  },
  Auditor: {
    group: 'Identity-Auditors',
    level: 1,
    badgeClass: 'badge-muted',
    permissions: ['users:read', 'audit:read', 'governance:read']
  },
  RoleManager: {
    group: 'Identity-Role-Managers',
    level: 4,
    badgeClass: 'badge-preview',
    permissions: ['roles:assign', 'policies:manage', 'governance:write', 'audit:read']
  }
};

function resolveUserRole(user, groups = []) {
  // If user profile has title/department or group hints
  const email = (user.profile?.email || '').toLowerCase();
  if (email.includes('admin') || user.profile?.title?.toLowerCase().includes('admin')) {
    return 'Admin';
  }
  if (email.includes('role') || user.profile?.title?.toLowerCase().includes('governance')) {
    return 'RoleManager';
  }
  if (email.includes('manager') || user.profile?.department?.toLowerCase().includes('management')) {
    return 'Manager';
  }
  if (email.includes('audit') || user.profile?.title?.toLowerCase().includes('auditor')) {
    return 'Auditor';
  }
  return 'Manager'; // Default operational role
}

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

// ── Confirmation Modal ────────────────────────────────────────────────────────

function ConfirmDialog({ isOpen, title, message, confirmText, isDanger, onConfirm, onCancel, loading }) {
  if (!isOpen) return null;
  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 440 }}>
        <h3 className="modal-title" style={{ marginBottom: 12 }}>{title}</h3>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 24 }}>
          {message}
        </p>
        <div className="modal-footer" style={{ marginTop: 0 }}>
          <button className="btn btn-secondary" onClick={onCancel} disabled={loading}>
            Cancel
          </button>
          <button
            className={`btn ${isDanger ? 'btn-danger' : 'btn-primary'}`}
            onClick={onConfirm}
            disabled={loading}
          >
            {loading ? 'Processing…' : confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main User Details Component ───────────────────────────────────────────────

function UserDetails() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [user, setUser]                 = useState(null);
  const [passwordInfo, setPasswordInfo] = useState(null);
  const [timeline, setTimeline]         = useState([]);
  const [loading, setLoading]           = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError]               = useState('');
  const [policyError, setPolicyError]   = useState(null);

  // Dialog states
  const [confirmDialog, setConfirmDialog] = useState({ isOpen: false });

  const loadUserData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const userData = await getUserById(id);
      if (!userData) {
        throw new Error(`User with ID ${id} not found.`);
      }
      setUser(userData);

      const email = userData.profile?.email || userData.profile?.login || '';
      
      // Parallel fetch password info and audit timeline
      const [pwd, logs] = await Promise.all([
        getUserPasswordExpiry(id).catch(() => null),
        getUserTimeline(id, email).catch(() => [])
      ]);

      setPasswordInfo(pwd);
      setTimeline(logs || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadUserData();
  }, [loadUserData]);

  // Actions
  const handleAction = async (actionType) => {
    setActionLoading(true);
    setConfirmDialog({ isOpen: false });
    try {
      if (actionType === 'provision') {
        await provisionUser(id);
      } else if (actionType === 'deactivate') {
        await deactivateUser(id);
      } else if (actionType === 'delete') {
        await deleteUser(id);
        navigate('/users');
        return;
      } else if (actionType === 'expire_password') {
        await expireUserPassword(id);
      }
      await loadUserData();
    } catch (err) {
      if (err.status === 403 || err.policy) {
        setPolicyError(err);
      } else {
        alert(`Action failed: ${err.message}`);
      }
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="user-details-page">
        <div className="page-header flex items-center justify-between">
          <div className="flex items-center gap-sm">
            <Link to="/users" className="btn btn-secondary btn-sm">
              <ArrowLeft size={14} /> Back to Users
            </Link>
          </div>
          <RotateMark size={28} isLoading={true} />
        </div>
        <div className="loading-row">Loading identity profile…</div>
      </div>
    );
  }

  if (error || !user) {
    return (
      <div className="user-details-page">
        <div className="page-header">
          <Link to="/users" className="btn btn-secondary btn-sm" style={{ marginBottom: 16 }}>
            <ArrowLeft size={14} /> Back to Users
          </Link>
          <div className="error-box">⚠ {error || 'User profile not found.'}</div>
        </div>
      </div>
    );
  }

  const p = user.profile || {};
  const roleName = resolveUserRole(user);
  const roleConfig = ROLE_DEFINITIONS[roleName] || ROLE_DEFINITIONS.Manager;

  return (
    <div className="user-details-page">
      {/* Header */}
      <div className="page-header flex items-center justify-between">
        <div className="flex items-center gap-md">
          <Link to="/users" className="btn btn-secondary btn-sm" title="Back to directory">
            <ArrowLeft size={14} /> Users Directory
          </Link>
          <div>
            <h1 className="page-title">{p.firstName} {p.lastName}</h1>
            <p className="page-subtitle">{p.email || p.login} · Okta ID: {user.id}</p>
          </div>
        </div>
        <div className="flex items-center gap-sm">
          <RotateMark size={28} isLoading={actionLoading} />
          <button className="btn btn-secondary btn-sm" onClick={loadUserData} title="Refresh profile">
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* 3-Column Profile Matrix */}
      <div className="profile-grid-3" style={{ marginBottom: 24 }}>
        {/* 1. Identity Overview */}
        <div className="card profile-card">
          <div className="profile-card-header">
            <div className="profile-card-icon">
              <User size={18} color="var(--mark-color-a)" />
            </div>
            <h3 className="section-title">Identity Overview</h3>
          </div>
          <div className="profile-info-list">
            <div className="info-item">
              <span className="info-label">Full Name</span>
              <span className="info-val font-semibold">{p.firstName} {p.lastName}</span>
            </div>
            <div className="info-item">
              <span className="info-label">Primary Email</span>
              <span className="info-val">{p.email || '—'}</span>
            </div>
            <div className="info-item">
              <span className="info-label">Login Username</span>
              <span className="info-val font-mono">{p.login || '—'}</span>
            </div>
            <div className="info-item">
              <span className="info-label">Account Status</span>
              <span className="info-val">
                <span className={`badge ${user.status?.toUpperCase() === 'ACTIVE' ? 'badge-active' : user.status?.toUpperCase() === 'DEPROVISIONED' ? 'badge-deprovisioned' : 'badge-staged'}`}>
                  {user.status}
                </span>
              </span>
            </div>
            <div className="info-item">
              <span className="info-label">Department</span>
              <span className="info-val">{p.department || 'General Staff'}</span>
            </div>
          </div>
        </div>

        {/* 2. Authorization & RBAC */}
        <div className="card profile-card">
          <div className="profile-card-header">
            <div className="profile-card-icon">
              <Shield size={18} color="var(--mark-color-b)" />
            </div>
            <h3 className="section-title">Authorization & RBAC</h3>
          </div>
          <div className="profile-info-list">
            <div className="info-item">
              <span className="info-label">Assigned Role</span>
              <span className="info-val">
                <span className={`badge ${roleConfig.badgeClass}`}>
                  {roleName} (Level {roleConfig.level})
                </span>
              </span>
            </div>
            <div className="info-item">
              <span className="info-label">Okta Group Mapping</span>
              <span className="info-val font-mono" style={{ color: 'var(--mark-color-a)', fontWeight: 600 }}>
                {roleConfig.group}
              </span>
            </div>
            <div className="info-item" style={{ marginTop: 4 }}>
              <span className="info-label">Effective Permissions</span>
              <div className="permissions-pills">
                {roleConfig.permissions.map((perm) => (
                  <span key={perm} className="perm-pill">{perm}</span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* 3. Security & Password Expiry */}
        <div className="card profile-card">
          <div className="profile-card-header">
            <div className="profile-card-icon">
              <Key size={18} color="var(--status-warning)" />
            </div>
            <h3 className="section-title">Security & Password</h3>
          </div>
          <div className="profile-info-list">
            <div className="info-item">
              <span className="info-label">Password Policy Status</span>
              <span className="info-val">
                <span className={`badge ${passwordInfo?.status === 'ACTIVE' ? 'badge-success' : passwordInfo?.status === 'EXPIRED' ? 'badge-danger' : 'badge-warning'}`}>
                  {passwordInfo?.status || 'MONITORED'}
                </span>
              </span>
            </div>
            <div className="info-item">
              <span className="info-label">Days Remaining</span>
              <span className="info-val font-bold" style={{ fontSize: 16 }}>
                {passwordInfo?.days_remaining != null ? `${passwordInfo.days_remaining} days` : 'N/A'}
              </span>
            </div>
            <div className="info-item">
              <span className="info-label">Next Expiry Date</span>
              <span className="info-val" style={{ fontSize: 12 }}>
                {passwordInfo?.expiry_date ? formatDate(passwordInfo.expiry_date) : 'Standard 90d cycle'}
              </span>
            </div>
            <div style={{ marginTop: 12 }}>
              <button
                className="btn btn-secondary btn-sm"
                style={{ width: '100%', justifyContent: 'center' }}
                onClick={() => setConfirmDialog({
                  isOpen: true,
                  title: 'Force Password Expiry',
                  message: `Are you sure you want to expire the password for ${p.email}? The user will be prompted to set a new password on their next login.`,
                  confirmText: 'Expire Password Now',
                  isDanger: false,
                  action: 'expire_password'
                })}
              >
                <Lock size={14} /> Force Password Expiry
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Lifecycle Actions Bar */}
      <div className="card lifecycle-actions-bar" style={{ marginBottom: 28 }}>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="section-title">Lifecycle Operations</h3>
            <p className="page-subtitle" style={{ margin: 0 }}>
              Trigger policy-controlled identity lifecycle transitions for this user.
            </p>
          </div>
          <div className="flex items-center gap-sm">
            <button
              className="btn btn-secondary btn-sm"
              disabled={actionLoading || user.status === 'ACTIVE'}
              onClick={() => setConfirmDialog({
                isOpen: true,
                title: 'Provision Identity',
                message: `Activate and provision ${p.email} in Okta?`,
                confirmText: 'Provision',
                isDanger: false,
                action: 'provision'
              })}
            >
              <Zap size={14} /> Provision
            </button>
            <button
              className="btn btn-secondary btn-sm"
              disabled={actionLoading || user.status === 'DEPROVISIONED'}
              onClick={() => setConfirmDialog({
                isOpen: true,
                title: 'Suspend / Deprovision User',
                message: `Suspend active access for ${p.email}? The account will be deactivated in Okta.`,
                confirmText: 'Deprovision User',
                isDanger: true,
                action: 'deactivate'
              })}
            >
              <UserMinus size={14} /> Deprovision
            </button>
            <button
              className="btn btn-danger btn-sm"
              disabled={actionLoading}
              onClick={() => setConfirmDialog({
                isOpen: true,
                title: 'Permanently Delete User',
                message: `Are you sure you want to permanently delete ${p.email}? This action cannot be undone.`,
                confirmText: 'Delete Permanently',
                isDanger: true,
                action: 'delete'
              })}
            >
              <Trash2 size={14} /> Delete User
            </button>
          </div>
        </div>
      </div>

      {/* Identity Timeline */}
      <div className="card timeline-card">
        <div className="flex items-center justify-between" style={{ marginBottom: 20 }}>
          <div className="flex items-center gap-sm">
            <Clock size={18} color="var(--mark-color-a)" />
            <h3 className="section-title">Identity Lifecycle Timeline</h3>
          </div>
          <span className="badge badge-muted">{timeline.length} Events Logged</span>
        </div>

        {timeline.length === 0 ? (
          <div className="loading-row" style={{ color: 'var(--text-muted)' }}>
            No recorded lifecycle events found for this identity in audit logs.
          </div>
        ) : (
          <div className="timeline-container">
            {timeline.map((item, idx) => {
              const isSuccess = item.status?.toUpperCase() === 'SUCCESS';
              return (
                <div key={item.id || idx} className="timeline-item">
                  <div className="timeline-marker">
                    <div className={`timeline-dot ${isSuccess ? 'dot-success' : 'dot-danger'}`}>
                      {isSuccess ? <Check size={10} color="#fff" /> : <AlertCircle size={10} color="#fff" />}
                    </div>
                    {idx < timeline.length - 1 && <div className="timeline-connector" />}
                  </div>
                  <div className="timeline-content">
                    <div className="flex items-center justify-between" style={{ marginBottom: 4 }}>
                      <span className="timeline-action">{item.action}</span>
                      <span className="timeline-timestamp">{formatDate(item.created_at)}</span>
                    </div>
                    <p className="timeline-msg">{item.message || 'Operation executed successfully.'}</p>
                    {(item.old_value || item.new_value) && (
                      <div className="timeline-transition">
                        <span>Transition:</span>
                        <code>{item.old_value || 'None'} → {item.new_value || 'None'}</code>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Confirmation Dialog */}
      <ConfirmDialog
        isOpen={confirmDialog.isOpen}
        title={confirmDialog.title}
        message={confirmDialog.message}
        confirmText={confirmDialog.confirmText}
        isDanger={confirmDialog.isDanger}
        loading={actionLoading}
        onConfirm={() => handleAction(confirmDialog.action)}
        onCancel={() => setConfirmDialog({ isOpen: false })}
      />

      {/* Policy Violation 403 Modal */}
      <PolicyViolationModal
        isOpen={!!policyError}
        error={policyError}
        onClose={() => setPolicyError(null)}
      />
    </div>
  );
}

export default UserDetails;
