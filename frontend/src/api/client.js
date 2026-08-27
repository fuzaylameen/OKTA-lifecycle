/**
 * IntelliID API Client
 *
 * Connected directly to verified FastAPI backend routers:
 *  - Auth:      /api/auth/token, /api/auth/me
 *  - Users:     /api/users/, /all, /deprovisioned, /:id/provision, /:id/suspend,
 *               /:id/reactivate, /:id/deactivate, /:id, /:id/role,
 *               /password-expiry, /:id/password-expiry, /:id/expire-password
 *  - Groups:    /api/groups/, /api/groups/move
 *  - Logs:      /api/logs/, /api/logs/authz
 *  - Bulk:      /api/bulk/users/provision, /deactivate, /, /import-csv
 *  - Export:    /api/export/users.csv
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const TOKEN_KEY = 'intelliid_auth_token';
const USER_KEY  = 'intelliid_auth_user';

// ─── Token helpers ────────────────────────────────────────────────────────────

export const getAuthToken = () => localStorage.getItem(TOKEN_KEY);
export const setAuthToken = (token) => {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
};

export const getStoredUser = () => {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (_) {
    return null;
  }
};

export const setStoredUser = (user) => {
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
  else localStorage.removeItem(USER_KEY);
};

// ─── Core request helper ──────────────────────────────────────────────────────

async function request(path, options = {}) {
  const url = `${BASE_URL}${path}`;
  const headers = { 'Content-Type': 'application/json', ...options.headers };

  const token = getAuthToken();
  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(url, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    let policy = null;
    let reason = null;

    try {
      const err = await res.json();
      if (typeof err.detail === 'string') {
        detail = err.detail;
      } else if (typeof err.detail === 'object' && err.detail !== null) {
        policy = err.detail.policy || null;
        reason = err.detail.reason || null;
        detail = err.detail.message || reason || JSON.stringify(err.detail);
      }
    } catch (_) { /* ignore parse error */ }

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

// ─── Authentication ───────────────────────────────────────────────────────────

export const loginWithEmail = async (email) => {
  const data = await request('/api/auth/token', {
    method: 'POST',
    body: JSON.stringify({ email: email.trim() }),
  });

  if (data?.access_token) {
    setAuthToken(data.access_token);
    setStoredUser(data);
  }
  return data;
};

export const logout = () => {
  setAuthToken(null);
  setStoredUser(null);
};

export const getCurrentUser = async () => {
  try {
    const data = await request('/api/auth/me');
    if (data) {
      const stored = getStoredUser() || {};
      const merged = { ...stored, ...data };
      setStoredUser(merged);
      return merged;
    }
  } catch (_) {
    // Fall back to stored session if network fails
  }

  return getStoredUser() || null;
};

// ─── Logs & Security Authorization Audit ──────────────────────────────────────

export const listLogs = () => request('/api/logs/');
export const listAuthzLogs = () => request('/api/logs/authz');

// ─── Users ────────────────────────────────────────────────────────────────────

export const listUsers = () => request('/api/users/');
export const listAllUsers = () => request('/api/users/all');
export const listDeprovisionedUsers = () => request('/api/users/deprovisioned');

export const getUserById = async (userId) => {
  const all = await listAllUsers();
  return all.find((u) => u.id === userId) || null;
};

export const createUser = (data) =>
  request('/api/users/', {
    method: 'POST',
    body: JSON.stringify({
      first_name: data.first_name || data.firstName,
      last_name:  data.last_name  || data.lastName,
      email:      data.email,
    }),
  });

export const provisionUser = (userId) =>
  request(`/api/users/${userId}/provision`, { method: 'POST' });

export const suspendUser = (userId, reason) =>
  request(`/api/users/${userId}/suspend`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });

export const reactivateUser = (userId) =>
  request(`/api/users/${userId}/reactivate`, { method: 'POST' });

export const deactivateUser = (userId) =>
  request(`/api/users/${userId}/deactivate`, { method: 'POST' });

export const deleteUser = (userId) =>
  request(`/api/users/${userId}`, { method: 'DELETE' });

export const assignUserRole = (userId, role) =>
  request(`/api/users/${userId}/role`, {
    method: 'POST',
    body: JSON.stringify({ role }),
  });

export const listPasswordExpiry = () => request('/api/users/password-expiry');

export const getUserPasswordExpiry = (userId) =>
  request(`/api/users/${userId}/password-expiry`);

export const expireUserPassword = (userId) =>
  request(`/api/users/${userId}/expire-password`, { method: 'POST' });

export const getUserTimeline = async (userId, email) => {
  const logs = await listLogs();
  return logs.filter((log) => {
    const idMatch    = userId && log.user_id === String(userId);
    const emailMatch = email  && log.user_email &&
                       log.user_email.toLowerCase() === email.toLowerCase();
    return idMatch || emailMatch;
  });
};

// ─── Groups ───────────────────────────────────────────────────────────────────

export const listGroups = () => request('/api/groups/');

export const moveUser = (userId, oldGroupId, newGroupId) =>
  request('/api/groups/move', {
    method: 'POST',
    body: JSON.stringify({
      user_id:      userId,
      old_group_id: oldGroupId,
      new_group_id: newGroupId,
    }),
  });

// ─── Bulk Operations ──────────────────────────────────────────────────────────

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
  const token = getAuthToken();
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${BASE_URL}/api/bulk/users/import-csv`, {
    method: 'POST',
    headers,
    body: formData,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try { const e = await res.json(); detail = e.detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
};

// ─── Export ───────────────────────────────────────────────────────────────────

export const exportUsersCSVUrl = () => `${BASE_URL}/api/export/users.csv`;
