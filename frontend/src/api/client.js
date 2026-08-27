/**
 * IntelliID API Client
 *
 * A thin fetch wrapper that reads VITE_API_BASE_URL from the .env file.
 * All functions return parsed JSON (or throw a descriptive Error).
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// ─── Core request helper ──────────────────────────────────────────────────────

async function request(path, options = {}) {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    let policy = null;
    let reason = null;

    try {
      const err = await res.json();
      detail = err.detail || JSON.stringify(err);
      if (typeof err.detail === 'object' && err.detail !== null) {
        policy = err.detail.policy || null;
        reason = err.detail.reason || null;
        detail = err.detail.message || reason || detail;
      }
    } catch (_) { /* ignore parse errors */ }

    const error = new Error(detail);
    error.status = res.status;
    error.policy = policy;
    error.reason = reason;
    throw error;
  }

  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return res.json();
  }
  return null;
}

// ─── Auth & Current Identity ──────────────────────────────────────────────────

export const getCurrentUser = async () => {
  try {
    return await request('/api/auth/me');
  } catch (err) {
    // If backend doesn't have /api/auth/me yet, return default demo admin identity
    return {
      id: '00u-current-user',
      name: 'Security Admin',
      email: 'admin@okta-identity.local',
      role: 'Admin',
      okta_group: 'Identity-Admins',
      privilege_level: 3,
      permissions: ['users:read', 'users:write', 'users:lifecycle', 'audit:read'],
    };
  }
};

// ─── Users ────────────────────────────────────────────────────────────────────

export const listUsers = () => request('/api/users/');
export const listAllUsers = () => request('/api/users/all');
export const listDeprovisionedUsers = () => request('/api/users/deprovisioned');

export const getUserById = async (userId) => {
  try {
    return await request(`/api/users/${userId}`);
  } catch (_) {
    // Fallback: lookup in all users list
    const all = await listAllUsers();
    return all.find((u) => u.id === userId) || null;
  }
};

export const createUser = (data) =>
  request('/api/users/', { method: 'POST', body: JSON.stringify(data) });

export const provisionUser = (userId) =>
  request(`/api/users/${userId}/provision`, { method: 'POST' });

export const deactivateUser = (userId) =>
  request(`/api/users/${userId}/deactivate`, { method: 'POST' });

export const deleteUser = (userId) =>
  request(`/api/users/${userId}`, { method: 'DELETE' });

export const listPasswordExpiry = () => request('/api/users/password-expiry');
export const getUserPasswordExpiry = (userId) =>
  request(`/api/users/${userId}/password-expiry`);

export const expireUserPassword = (userId) =>
  request(`/api/users/${userId}/expire-password`, { method: 'POST' });

// ─── User Timeline (composed from real audit logs) ────────────────────────────

export const getUserTimeline = async (userId, email) => {
  const logs = await listLogs();
  return logs.filter((log) => {
    return (
      (userId && log.user_id === userId) ||
      (email && log.user_email && log.user_email.toLowerCase() === email.toLowerCase())
    );
  });
};

// ─── Groups ───────────────────────────────────────────────────────────────────

export const listGroups = () => request('/api/groups/');

export const moveUser = (userId, oldGroupId, newGroupId) =>
  request('/api/groups/move', {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, old_group_id: oldGroupId, new_group_id: newGroupId }),
  });

// ─── Logs ─────────────────────────────────────────────────────────────────────

export const listLogs = () => request('/api/logs/');

// ─── Bulk ─────────────────────────────────────────────────────────────────────

export const bulkProvision = (userIds) =>
  request('/api/bulk/users/provision', {
    method: 'POST',
    body: JSON.stringify({ user_ids: userIds }),
  });

export const bulkDeactivate = (userIds) =>
  request('/api/bulk/users/deactivate', {
    method: 'POST',
    body: JSON.stringify({ user_ids: userIds }),
  });

export const bulkDelete = (userIds) =>
  request('/api/bulk/users/', {
    method: 'DELETE',
    body: JSON.stringify({ user_ids: userIds }),
  });

export const importUsersCSV = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  const url = `${BASE_URL}/api/bulk/users/import-csv`;
  const res = await fetch(url, { method: 'POST', body: formData });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try { const e = await res.json(); detail = e.detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
};

// ─── Export ───────────────────────────────────────────────────────────────────

export const exportUsersCSVUrl = () => `${BASE_URL}/api/export/users.csv`;

// ─── Lifecycle Execution API ──────────────────────────────────────────────────

export const lifecycleDryRun = async (payload) => {
  try {
    return await request('/api/lifecycle/dry-run', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  } catch (err) {
    if (err.status === 404 || err.message.includes('404')) {
      console.warn('Frontend requires backend endpoint POST /api/lifecycle/dry-run');
    }
    throw err;
  }
};

export const getLifecycleOperation = async (operationId) => {
  try {
    return await request(`/api/lifecycle/${operationId}`);
  } catch (err) {
    if (err.status === 404 || err.message.includes('404')) {
      console.warn(`Frontend requires backend endpoint GET /api/lifecycle/${operationId}`);
    }
    throw err;
  }
};

export const confirmLifecycle = async (operationId) => {
  try {
    return await request(`/api/lifecycle/${operationId}/confirm`, { method: 'POST' });
  } catch (err) {
    if (err.status === 404 || err.message.includes('404')) {
      console.warn(`Frontend requires backend endpoint POST /api/lifecycle/${operationId}/confirm`);
    }
    throw err;
  }
};

export const cancelLifecycle = async (operationId) => {
  try {
    return await request(`/api/lifecycle/${operationId}/cancel`, { method: 'POST' });
  } catch (err) {
    if (err.status === 404 || err.message.includes('404')) {
      console.warn(`Frontend requires backend endpoint POST /api/lifecycle/${operationId}/cancel`);
    }
    throw err;
  }
};

export const verifyLifecycle = async (operationId) => {
  try {
    return await request(`/api/lifecycle/${operationId}/verify`);
  } catch (err) {
    if (err.status === 404 || err.message.includes('404')) {
      console.warn(`Frontend requires backend endpoint GET /api/lifecycle/${operationId}/verify`);
    }
    throw err;
  }
};

// ─── Approvals API ────────────────────────────────────────────────────────────

export const listApprovals = async () => {
  try {
    return await request('/api/approvals');
  } catch (err) {
    if (err.status === 404 || err.message.includes('404')) {
      console.warn('Frontend requires backend endpoint GET /api/approvals');
    }
    throw err;
  }
};

export const approveRequest = async (requestId) => {
  return request(`/api/approvals/${requestId}/approve`, { method: 'POST' });
};

export const rejectRequest = async (requestId, reason = '') => {
  return request(`/api/approvals/${requestId}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
};

export const escalateRequest = async (requestId) => {
  return request(`/api/approvals/${requestId}/escalate`, { method: 'POST' });
};
