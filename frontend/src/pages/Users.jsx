import { useEffect, useState, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  listUsers, listAllUsers, listDeprovisionedUsers,
  createUser, provisionUser, deactivateUser, deleteUser,
  expireUserPassword, bulkProvision, bulkDeactivate, bulkDelete,
  importUsersCSV, exportUsersCSVUrl,
} from '../api/client';
import RotateMark from '../components/RotateMark';
import PolicyViolationModal from '../components/PolicyViolationModal';
import {
  Search, Plus, Download, Upload, RefreshCw,
  Zap, UserMinus, Trash2, Lock, X, ChevronRight
} from 'lucide-react';
import './Users.css';

// ── Helpers ───────────────────────────────────────────────────────────────────

const ROLE_MAP = {
  Admin: { group: 'Identity-Admins', class: 'badge-provisioned' },
  Manager: { group: 'Identity-Managers', class: 'badge-active' },
  Auditor: { group: 'Identity-Auditors', class: 'badge-muted' },
  RoleManager: { group: 'Identity-Role-Managers', class: 'badge-preview' },
};

function resolveRoleAndGroup(user) {
  const role = user.role || 'Unassigned';
  const group = user.primary_group || user.okta_groups?.[0] || 'Everyone';

  const badgeClass =
    role === 'Admin'       ? 'badge-provisioned' :
    role === 'RoleManager' ? 'badge-preview' :
    role === 'Manager'     ? 'badge-active' :
    role === 'Auditor'     ? 'badge-muted' : 'badge-muted';

  return {
    role,
    group,
    class: badgeClass,
  };
}

function StatusBadge({ status }) {
  if (!status) return <span className="badge badge-muted">—</span>;
  const s = status.toUpperCase();
  const cls =
    s === 'ACTIVE'        ? 'badge-active'        :
    s === 'PROVISIONED'   ? 'badge-provisioned'   :
    s === 'DEPROVISIONED' ? 'badge-deprovisioned' :
    s === 'STAGED'        ? 'badge-staged'        : 'badge-muted';
  return <span className={`badge ${cls}`}>{status}</span>;
}

// ── Smooth Table Skeleton Loader ──────────────────────────────────────────────

function TableSkeletonRows({ count = 5 }) {
  return Array.from({ length: count }, (_, i) => (
    <tr key={i} className="skeleton-row">
      <td style={{ width: 40 }}>
        <div className="skeleton" style={{ width: 16, height: 16, borderRadius: 4 }} />
      </td>
      <td>
        <div className="user-name-cell">
          <div className="skeleton" style={{ width: 32, height: 32, borderRadius: '50%' }} />
          <div className="skeleton" style={{ width: 120, height: 14, borderRadius: 4 }} />
        </div>
      </td>
      <td><div className="skeleton" style={{ width: 160, height: 14, borderRadius: 4 }} /></td>
      <td><div className="skeleton" style={{ width: 80, height: 20, borderRadius: 10 }} /></td>
      <td><div className="skeleton" style={{ width: 130, height: 14, borderRadius: 4 }} /></td>
      <td><div className="skeleton" style={{ width: 75, height: 20, borderRadius: 10 }} /></td>
      <td>
        <div className="flex items-center gap-sm">
          <div className="skeleton" style={{ width: 28, height: 28, borderRadius: 6 }} />
          <div className="skeleton" style={{ width: 28, height: 28, borderRadius: 6 }} />
          <div className="skeleton" style={{ width: 28, height: 28, borderRadius: 6 }} />
        </div>
      </td>
    </tr>
  ));
}

// ── Create User Modal ─────────────────────────────────────────────────────────

function CreateUserModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    firstName: '', lastName: '', email: '', login: '',
    department: '', title: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await createUser({
        first_name: form.firstName,
        last_name:  form.lastName,
        email:      form.email,
        // Note: backend only accepts first_name, last_name, email
        // login defaults to email, department/title are not in the schema
      });
      onCreated();
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
          <h3 className="modal-title">Create New User Profile</h3>
          <button className="btn-icon" onClick={onClose}><X size={16} /></button>
        </div>

        {error && <div className="error-box" style={{ marginBottom: 16 }}>{error}</div>}

        <form onSubmit={handleSubmit}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div className="form-group">
              <label className="form-label">First Name *</label>
              <input required value={form.firstName} onChange={set('firstName')} placeholder="Jane" />
            </div>
            <div className="form-group">
              <label className="form-label">Last Name *</label>
              <input required value={form.lastName} onChange={set('lastName')} placeholder="Doe" />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Email *</label>
            <input required type="email" value={form.email} onChange={set('email')} placeholder="jane.doe@corp.com" />
          </div>
          <div className="form-group">
            <label className="form-label">Login (defaults to email)</label>
            <input value={form.login} onChange={set('login')} placeholder="jane.doe@corp.com" />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div className="form-group">
              <label className="form-label">Department</label>
              <input value={form.department} onChange={set('department')} placeholder="Engineering" />
            </div>
            <div className="form-group">
              <label className="form-label">Title / Role Hint</label>
              <input value={form.title} onChange={set('title')} placeholder="Security Admin" />
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Creating…' : 'Create User'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

function Users() {
  const navigate = useNavigate();
  const [tab, setTab]               = useState('all');
  const [users, setUsers]           = useState([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState('');
  const [search, setSearch]         = useState('');
  const [selected, setSelected]     = useState(new Set());
  const [showCreate, setShowCreate] = useState(false);
  const [actionLoading, setActionLoading] = useState('');
  const [policyError, setPolicyError] = useState(null);
  const fileInputRef                = useRef();

  const fetchUsers = async (currentTab = tab) => {
    setLoading(true);
    setError('');
    try {
      const data =
        currentTab === 'all'          ? await listAllUsers() :
        currentTab === 'deprovisioned'? await listDeprovisionedUsers() :
                                        await listUsers();
      setUsers(data || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchUsers(tab); }, [tab]); // eslint-disable-line

  const filtered = users.filter((u) => {
    if (!search) return true;
    const q = search.toLowerCase();
    const p = u.profile || {};
    return (
      (p.firstName || '').toLowerCase().includes(q) ||
      (p.lastName  || '').toLowerCase().includes(q) ||
      (p.email     || '').toLowerCase().includes(q) ||
      (u.id        || '').toLowerCase().includes(q)
    );
  });

  const toggleSelect = (id, e) => {
    e.stopPropagation();
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === filtered.length) setSelected(new Set());
    else setSelected(new Set(filtered.map((u) => u.id)));
  };

  const doAction = async (userId, action, e) => {
    if (e) e.stopPropagation();
    setActionLoading(userId + action);
    try {
      if (action === 'provision')       await provisionUser(userId);
      else if (action === 'deactivate') await deactivateUser(userId);
      else if (action === 'delete')     await deleteUser(userId);
      else if (action === 'expire')     await expireUserPassword(userId);
      await fetchUsers(tab);
    } catch (err) {
      if (err.status === 403 || err.policy) {
        setPolicyError(err);
      } else {
        alert(`Operation failed: ${err.message}`);
      }
    } finally {
      setActionLoading('');
    }
  };

  const doBulk = async (action) => {
    const ids = [...selected];
    if (!ids.length) return;
    setActionLoading('bulk-' + action);
    try {
      if (action === 'provision')       await bulkProvision(ids);
      else if (action === 'deactivate') await bulkDeactivate(ids);
      else if (action === 'delete')     await bulkDelete(ids);
      setSelected(new Set());
      await fetchUsers(tab);
    } catch (err) {
      if (err.status === 403 || err.policy) {
        setPolicyError(err);
      } else {
        alert(`Bulk ${action} failed: ${err.message}`);
      }
    } finally {
      setActionLoading('');
    }
  };

  const handleImport = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const result = await importUsersCSV(file);
      alert(`Import complete: ${JSON.stringify(result)}`);
      await fetchUsers(tab);
    } catch (err) {
      alert(`Import failed: ${err.message}`);
    }
    e.target.value = '';
  };

  return (
    <div className="users-page">
      {/* Header */}
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="page-title">Users Directory</h1>
          <p className="page-subtitle">
            {loading ? 'Fetching identities…' : `${filtered.length} user${filtered.length !== 1 ? 's' : ''} listed`}
          </p>
        </div>
        <div className="flex items-center gap-sm">
          <RotateMark size={28} isLoading={loading || !!actionLoading} />
          <button className="btn btn-secondary btn-sm" onClick={() => fetchUsers(tab)} title="Refresh">
            <RefreshCw size={14} />
          </button>
          <a href={exportUsersCSVUrl()} className="btn btn-secondary btn-sm" download>
            <Download size={14} /> Export CSV
          </a>
          <button className="btn btn-secondary btn-sm" onClick={() => fileInputRef.current?.click()}>
            <Upload size={14} /> Import CSV
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            style={{ display: 'none' }}
            onChange={handleImport}
          />
          <button className="btn btn-primary btn-sm" onClick={() => setShowCreate(true)}>
            <Plus size={15} /> New User
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs">
        {[
          { key: 'all',           label: 'All Users' },
          { key: 'active',        label: 'Active' },
          { key: 'deprovisioned', label: 'Deprovisioned' },
        ].map(({ key, label }) => (
          <button
            key={key}
            className={`tab ${tab === key ? 'active' : ''}`}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Search + Bulk Actions */}
      <div className="flex items-center justify-between" style={{ marginBottom: 16 }}>
        <div className="search-box" style={{ width: 320 }}>
          <Search size={15} className="search-icon" />
          <input
            placeholder="Search by name, email, or ID…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {selected.size > 0 && (
          <div className="flex items-center gap-sm" style={{ animation: 'fadeIn 0.2s ease' }}>
            <span className="badge badge-muted">{selected.size} selected</span>
            <button className="btn btn-secondary btn-sm" onClick={() => doBulk('provision')} disabled={!!actionLoading}>
              <Zap size={13} /> Provision
            </button>
            <button className="btn btn-secondary btn-sm" onClick={() => doBulk('deactivate')} disabled={!!actionLoading}>
              <UserMinus size={13} /> Deprovision
            </button>
            <button className="btn btn-danger btn-sm" onClick={() => doBulk('delete')} disabled={!!actionLoading}>
              <Trash2 size={13} /> Delete
            </button>
          </div>
        )}
      </div>

      {/* Error */}
      {error && <div className="error-box" style={{ marginBottom: 16 }}>⚠ {error}</div>}

      {/* Users Table: Name | Email | Role | Okta Group | Status | Actions */}
      <div className="card users-table-card">
        <table>
          <thead>
            <tr>
              <th style={{ width: 44 }}>
                <div className="checkbox-cell">
                  <input
                    type="checkbox"
                    checked={selected.size === filtered.length && filtered.length > 0}
                    onChange={toggleAll}
                  />
                </div>
              </th>
              <th>Name</th>
              <th>Email</th>
              <th>Role</th>
              <th>Okta Group</th>
              <th>Status</th>
              <th style={{ width: 140 }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <TableSkeletonRows count={5} />
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={7} className="loading-row" style={{ color: 'var(--text-muted)' }}>
                  No users found matching your filter.
                </td>
              </tr>
            ) : (
              filtered.map((user, idx) => {
                const p = user.profile || {};
                const { role, group, class: roleClass } = resolveRoleAndGroup(user);
                const isLoading = actionLoading.startsWith(user.id);
                return (
                  <tr
                    key={user.id}
                    className="user-row-animated clickable-row"
                    style={{ '--row-delay': `${Math.min(idx * 20, 250)}ms` }}
                    onClick={() => navigate(`/users/${user.id}`)}
                  >
                    <td onClick={(e) => e.stopPropagation()}>
                      <div className="checkbox-cell">
                        <input
                          type="checkbox"
                          checked={selected.has(user.id)}
                          onChange={(e) => toggleSelect(user.id, e)}
                        />
                      </div>
                    </td>
                    <td>
                      <div className="user-name-cell">
                        <span className="user-avatar">
                          {(p.firstName?.[0] || '?')}{(p.lastName?.[0] || '')}
                        </span>
                        <div className="flex flex-col">
                          <span className="user-fullname">{p.firstName} {p.lastName}</span>
                          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>ID: {user.id}</span>
                        </div>
                      </div>
                    </td>
                    <td>{p.email || '—'}</td>
                    <td>
                      <span className={`badge ${roleClass}`}>{role}</span>
                    </td>
                    <td>
                      <span className="font-mono text-secondary" style={{ fontSize: 12.5, fontWeight: 500 }}>
                        {group}
                      </span>
                    </td>
                    <td><StatusBadge status={user.status} /></td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center gap-sm">
                        <button
                          className="btn-icon" title="Provision Account"
                          disabled={isLoading || user.status === 'ACTIVE'}
                          onClick={(e) => doAction(user.id, 'provision', e)}
                        ><Zap size={14} /></button>
                        <button
                          className="btn-icon" title="Deprovision (Deactivate)"
                          disabled={isLoading || user.status === 'DEPROVISIONED'}
                          onClick={(e) => doAction(user.id, 'deactivate', e)}
                        ><UserMinus size={14} /></button>
                        <button
                          className="btn-icon" title="Force Password Expiry"
                          disabled={isLoading}
                          onClick={(e) => doAction(user.id, 'expire', e)}
                        ><Lock size={14} /></button>
                        <button
                          className="btn-icon" title="Delete User Permanently"
                          disabled={isLoading}
                          style={{ color: 'var(--status-danger)' }}
                          onClick={(e) => {
                            if (window.confirm(`Permanently delete ${p.email || user.id}?`))
                              doAction(user.id, 'delete', e);
                          }}
                        ><Trash2 size={14} /></button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Create modal */}
      {showCreate && (
        <CreateUserModal
          onClose={() => setShowCreate(false)}
          onCreated={() => fetchUsers(tab)}
        />
      )}

      {/* Policy 403 Violation Dialog */}
      <PolicyViolationModal
        isOpen={!!policyError}
        error={policyError}
        onClose={() => setPolicyError(null)}
      />
    </div>
  );
}

export default Users;
