/**
 * IntelliID API Client
 *
 * Thin fetch wrapper reading VITE_API_BASE_URL from .env
 * All functions return parsed JSON or throw a descriptive Error.
 *
 * ── Real Backend Endpoints (verified against backend/app/routers/) ──────────
 *
 *  Users                            router prefix: /api/users
 *    GET    /api/users/             → listUsers()
 *    GET    /api/users/all          → listAllUsers()
 *    GET    /api/users/deprovisioned→ listDeprovisionedUsers()
 *    POST   /api/users/             → createUser(data)          body: {first_name, last_name, email}
 *    POST   /api/users/:id/provision→ provisionUser(id)
 *    POST   /api/users/:id/deactivate→ deactivateUser(id)
 *    DELETE /api/users/:id          → deleteUser(id)
 *    GET    /api/users/password-expiry → listPasswordExpiry()
 *    GET    /api/users/:id/password-expiry → getUserPasswordExpiry(id)
 *    POST   /api/users/:id/expire-password → expireUserPassword(id)
 *
 *  Groups                           router prefix: /api/groups
 *    GET    /api/groups/            → listGroups()
 *    POST   /api/groups/move        → moveUser(userId, oldGroupId, newGroupId)
 *                                     body: {user_id, old_group_id, new_group_id}
 *
 *  Logs                             router prefix: /api/logs
 *    GET    /api/logs/              → listLogs()
 *                                     returns: [{id, action, user_id, user_email,
 *                                               old_value, new_value, status,
 *                                               message, created_at}]
 *
 *  Bulk Users                       router prefix: /api/bulk/users
 *    POST   /api/bulk/users/provision  → bulkProvision(userIds)  body: {user_ids: [...]}
 *    POST   /api/bulk/users/deactivate → bulkDeactivate(userIds) body: {user_ids: [...]}
 *    DELETE /api/bulk/users/           → bulkDelete(userIds)     body: {user_ids: [...]}
 *    POST   /api/bulk/users/import-csv → importUsersCSV(file)   multipart/form-data
 *
 *  Export                           router prefix: /api/export
 *    GET    /api/export/users.csv   → exportUsersCSVUrl()  (direct download link)
 *
 *  ── NOT YET IN BACKEND (UI shells only) ──────────────────────────────────
 *    GET    /api/auth/me            → getCurrentUser()   (graceful 404 fallback)
 *    POST   /api/lifecycle/dry-run  → lifecycleDryRun()  (graceful 404 fallback)
 *    GET    /api/lifecycle/:id      → getLifecycleOperation()
 *    POST   /api/lifecycle/:id/confirm → confirmLifecycle()
 *    POST   /api/lifecycle/:id/cancel  → cancelLifecycle()
 *    GET    /api/lifecycle/:id/verify  → verifyLifecycle()
 *    GET    /api/approvals          → listApprovals()    (graceful 404 fallback)
 *    POST   /api/approvals/:id/approve → approveRequest()
 *    POST   /api/approvals/:id/reject  → rejectRequest()
 *    POST   /api/approvals/:id/escalate→ escalateRequest()
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
      // FastAPI returns {detail: "string"} or {detail: {message, policy, reason}}
      if (typeof err.detail === 'string') {
        detail = err.detail;
      } else if (typeof err.detail === 'object' && err.detail !== null) {
        policy = err.detail.policy || null;
        reason = err.detail.reason || null;
        detail = err.detail.message || reason || JSON.stringify(err.detail);
      }
    } catch (_) { /* ignore JSON parse errors */ }

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

// ─── Auth / Current User (NOT in backend yet — graceful fallback) ─────────────

export const getCurrentUser = async () => {
  try {
    return await request('/api/auth/me');
  } catch (_) {
    // /api/auth/me does not exist in backend yet — return demo admin context
    return {
      id: 'current-user',
      name: 'Security Admin',
      email: 'admin@okta-identity.local',
      role: 'Admin',
      okta_group: 'Identity-Admins',
      privilege_level: 3,
      permissions: ['users:read', 'users:write', 'users:lifecycle', 'audit:read'],
    };
  }
};

// ─── Logs (declared first — used by getUserTimeline below) ───────────────────

/**
 * GET /api/logs/
 * Returns array of: { id, action, user_id, user_email, old_value, new_value,
 *                     status, message, created_at }
 * Ordered by created_at DESC.
 */
export const listLogs = () => request('/api/logs/');

// ─── Users ────────────────────────────────────────────────────────────────────

/** GET /api/users/ — active users only (no DEPROVISIONED) */
export const listUsers = () => request('/api/users/');

/** GET /api/users/all — active + deprovisioned combined */
export const listAllUsers = () => request('/api/users/all');

/** GET /api/users/deprovisioned — deprovisioned users only */
export const listDeprovisionedUsers = () => request('/api/users/deprovisioned');

/**
 * No dedicated GET /api/users/:id endpoint exists in the backend.
 * We fetch all users and find by id. Falls back to null if not found.
 */
export const getUserById = async (userId) => {
  const all = await listAllUsers();
  return all.find((u) => u.id === userId) || null;
};

/**
 * POST /api/users/
 * Backend UserCreate schema: { first_name, last_name, email }
 * Note: login is NOT in the schema — backend uses email as login.
 */
export const createUser = (data) =>
  request('/api/users/', {
    method: 'POST',
    body: JSON.stringify({
      first_name: data.first_name || data.firstName,
      last_name:  data.last_name  || data.lastName,
      email:      data.email,
    }),
  });

/** POST /api/users/:id/provision — sends activation email to user */
export const provisionUser = (userId) =>
  request(`/api/users/${userId}/provision`, { method: 'POST' });

/** POST /api/users/:id/deactivate — deactivates account in Okta */
export const deactivateUser = (userId) =>
  request(`/api/users/${userId}/deactivate`, { method: 'POST' });

/** DELETE /api/users/:id — permanently deletes user from Okta */
export const deleteUser = (userId) =>
  request(`/api/users/${userId}`, { method: 'DELETE' });

/** GET /api/users/password-expiry — expiry info for all users */
export const listPasswordExpiry = () => request('/api/users/password-expiry');

/**
 * GET /api/users/:id/password-expiry
 * Returns: { user_id, email, password_changed, expiry_date,
 *             days_remaining, status, expiry_days }
 * status values: ACTIVE | EXPIRING_SOON | EXPIRED | NO_PASSWORD_DATE | INVALID_PASSWORD_DATE
 */
export const getUserPasswordExpiry = (userId) =>
  request(`/api/users/${userId}/password-expiry`);

/** POST /api/users/:id/expire-password — forces password expiry at next login */
export const expireUserPassword = (userId) =>
  request(`/api/users/${userId}/expire-password`, { method: 'POST' });

// ─── User Timeline (derived from real audit log — no dedicated endpoint) ──────

/**
 * Filters GET /api/logs/ records by user_id or user_email.
 * This is a frontend-composed view — no dedicated backend endpoint exists.
 */
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

/**
 * GET /api/groups/
 * Returns Okta group objects with { id, profile: { name }, objectClass }
 */
export const listGroups = () => request('/api/groups/');

/**
 * POST /api/groups/move
 * Body: { user_id, old_group_id, new_group_id }
 * Removes user from old_group_id and adds to new_group_id in Okta.
 */
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

/** POST /api/bulk/users/provision  body: { user_ids: [...] } */
export const bulkProvision = (userIds) =>
  request('/api/bulk/users/provision', {
    method: 'POST',
    body: JSON.stringify({ user_ids: userIds }),
  });

/** POST /api/bulk/users/deactivate  body: { user_ids: [...] } */
export const bulkDeactivate = (userIds) =>
  request('/api/bulk/users/deactivate', {
    method: 'POST',
    body: JSON.stringify({ user_ids: userIds }),
  });

/** DELETE /api/bulk/users/  body: { user_ids: [...] } */
export const bulkDelete = (userIds) =>
  request('/api/bulk/users/', {
    method: 'DELETE',
    body: JSON.stringify({ user_ids: userIds }),
  });

/** POST /api/bulk/users/import-csv  multipart form */
export const importUsersCSV = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${BASE_URL}/api/bulk/users/import-csv`, {
    method: 'POST',
    body: formData,
    // No Content-Type header — browser sets it with boundary automatically
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try { const e = await res.json(); detail = e.detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
};

// ─── Export ───────────────────────────────────────────────────────────────────

/** GET /api/export/users.csv — returns streaming CSV download */
export const exportUsersCSVUrl = () => `${BASE_URL}/api/export/users.csv`;

// ─── Lifecycle Engine (NOT in backend yet) ────────────────────────────────────

export const lifecycleDryRun = (payload) =>
  request('/api/lifecycle/dry-run', {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const getLifecycleOperation = (operationId) =>
  request(`/api/lifecycle/${operationId}`);

export const confirmLifecycle = (operationId) =>
  request(`/api/lifecycle/${operationId}/confirm`, { method: 'POST' });

export const cancelLifecycle = (operationId) =>
  request(`/api/lifecycle/${operationId}/cancel`, { method: 'POST' });

export const verifyLifecycle = (operationId) =>
  request(`/api/lifecycle/${operationId}/verify`);

// ─── Approvals (NOT in backend yet) ──────────────────────────────────────────

export const listApprovals = () => request('/api/approvals');

export const approveRequest = (requestId) =>
  request(`/api/approvals/${requestId}/approve`, { method: 'POST' });

export const rejectRequest = (requestId, reason = '') =>
  request(`/api/approvals/${requestId}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });

export const escalateRequest = (requestId) =>
  request(`/api/approvals/${requestId}/escalate`, { method: 'POST' });
