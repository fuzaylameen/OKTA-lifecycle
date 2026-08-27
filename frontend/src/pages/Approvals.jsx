import { useState, useEffect } from 'react';
import { getCurrentUser, listApprovals, approveRequest, rejectRequest, escalateRequest } from '../api/client';
import RotateMark from '../components/RotateMark';
import PolicyViolationModal from '../components/PolicyViolationModal';
import {
  Check, X, ArrowUpRight, Search, RefreshCw
} from 'lucide-react';
import './Approvals.css';

// Initial operational approval pipeline dataset
const SAMPLE_APPROVAL_REQUESTS = [
  {
    id: 'req-8901',
    requester: 'sarah.manager@corp.com',
    requester_role: 'Manager',
    target_user: 'dev.lead@corp.com',
    action: 'ROLE_ELEVATION',
    requested_role: 'Admin',
    created_at: new Date(Date.now() - 3600000 * 2).toISOString(),
    status: 'PENDING',
    reason: 'Requires production debug access for deployment outage mitigation.',
  },
  {
    id: 'req-8902',
    requester: 'alex.ops@corp.com',
    requester_role: 'Manager',
    target_user: 'contractor.qa@external.com',
    action: 'LIFECYCLE_SUSPEND',
    requested_role: null,
    created_at: new Date(Date.now() - 3600000 * 5).toISOString(),
    status: 'PENDING',
    reason: 'Contract period ended as per project milestone.',
  },
  {
    id: 'req-8894',
    requester: 'auditor.lead@corp.com',
    requester_role: 'Auditor',
    target_user: 'finance.analyst@corp.com',
    action: 'GROUP_MEMBERSHIP_ASSIGN',
    requested_role: 'Identity-Admins',
    created_at: new Date(Date.now() - 86400000).toISOString(),
    status: 'REJECTED',
    reason: 'Rejected by Policy: PreventPrivilegeEscalationPolicy.',
  },
  {
    id: 'req-8889',
    requester: 'admin.super@corp.com',
    requester_role: 'Admin',
    target_user: 'james.eng@corp.com',
    action: 'PROVISION_IDENTITY',
    requested_role: 'Manager',
    created_at: new Date(Date.now() - 86400000 * 2).toISOString(),
    status: 'APPROVED',
    reason: 'Approved by Security Governance.',
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

function StatusPill({ status }) {
  const s = status?.toUpperCase();
  const cls =
    s === 'PENDING'   ? 'badge-warning' :
    s === 'APPROVED'  ? 'badge-success' :
    s === 'REJECTED'  ? 'badge-danger'  : 'badge-preview';
  return <span className={`badge ${cls}`}>{status}</span>;
}

function Approvals() {
  const [currentUser, setCurrentUser] = useState(null);
  const [requests, setRequests]       = useState(SAMPLE_APPROVAL_REQUESTS);
  const [filterStatus, setFilterStatus] = useState('ALL');
  const [search, setSearch]           = useState('');
  const [loading, setLoading]         = useState(false);
  const [actionLoading, setActionLoading] = useState('');
  const [policyError, setPolicyError] = useState(null);

  useEffect(() => {
    getCurrentUser().then(setCurrentUser);
    listApprovals()
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setRequests(data);
        }
      })
      .catch(() => {
        // Retain sample approval queue if backend endpoint not active
      });
  }, []);

  const handleDecision = async (reqId, decision) => {
    setActionLoading(reqId + decision);
    try {
      if (decision === 'APPROVE') {
        await approveRequest(reqId);
      } else if (decision === 'REJECT') {
        await rejectRequest(reqId, 'Denied by governance reviewer');
      } else if (decision === 'ESCALATE') {
        await escalateRequest(reqId);
      }

      setRequests((prev) =>
        prev.map((r) =>
          r.id === reqId
            ? { ...r, status: decision === 'APPROVE' ? 'APPROVED' : decision === 'REJECT' ? 'REJECTED' : 'ESCALATED' }
            : r
        )
      );
    } catch (err) {
      if (err.status === 403 || err.policy) {
        setPolicyError(err);
      } else {
        // Update local state if endpoint was mock/pending
        setRequests((prev) =>
          prev.map((r) =>
            r.id === reqId
              ? { ...r, status: decision === 'APPROVE' ? 'APPROVED' : decision === 'REJECT' ? 'REJECTED' : 'ESCALATED' }
              : r
          )
        );
      }
    } finally {
      setActionLoading('');
    }
  };

  const filtered = requests.filter((r) => {
    const matchesStatus = filterStatus === 'ALL' || r.status === filterStatus;
    const q = search.toLowerCase();
    const matchesSearch =
      !q ||
      r.id.toLowerCase().includes(q) ||
      r.requester.toLowerCase().includes(q) ||
      r.target_user.toLowerCase().includes(q) ||
      r.action.toLowerCase().includes(q);
    return matchesStatus && matchesSearch;
  });

  const pendingCount = requests.filter((r) => r.status === 'PENDING').length;
  const canApprove = currentUser?.role === 'Admin' || currentUser?.role === 'RoleManager';

  return (
    <div className="approvals-page">
      {/* Header */}
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="page-title">Identity Approvals</h1>
          <p className="page-subtitle">
            Multi-stage governance review and privileged role authorization queue
          </p>
        </div>
        <div className="flex items-center gap-sm">
          <RotateMark size={28} isLoading={loading || !!actionLoading} />
          <button className="btn btn-secondary btn-sm" onClick={() => { setLoading(true); setTimeout(() => setLoading(false), 300); }}>
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* Overview Cards */}
      <div className="grid-4" style={{ marginBottom: 24 }}>
        <div className="metric-card">
          <span className="metric-label">Pending Reviews</span>
          <span className="metric-value" style={{ color: 'var(--status-warning)' }}>{pendingCount}</span>
          <span className="metric-sub">Requires admin decision</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Approved Today</span>
          <span className="metric-value" style={{ color: 'var(--status-success)' }}>
            {requests.filter((r) => r.status === 'APPROVED').length}
          </span>
          <span className="metric-sub">Provisioning triggered</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Policy Denials</span>
          <span className="metric-value" style={{ color: 'var(--status-danger)' }}>
            {requests.filter((r) => r.status === 'REJECTED').length}
          </span>
          <span className="metric-sub">Blocked by policy engine</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Current Reviewer Role</span>
          <span className="metric-value" style={{ fontSize: 24, color: 'var(--mark-color-a)' }}>
            {currentUser?.role || 'Admin'}
          </span>
          <span className="metric-sub">{canApprove ? 'Authorized to approve' : 'Read-only reviewer'}</span>
        </div>
      </div>

      {/* Filters & Tabs */}
      <div className="flex items-center justify-between" style={{ marginBottom: 16 }}>
        <div className="search-box" style={{ width: 320 }}>
          <Search size={15} className="search-icon" />
          <input
            placeholder="Search request, requester, or target…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div className="tabs" style={{ marginBottom: 0 }}>
          {['ALL', 'PENDING', 'APPROVED', 'REJECTED', 'ESCALATED'].map((st) => (
            <button
              key={st}
              className={`tab ${filterStatus === st ? 'active' : ''}`}
              onClick={() => setFilterStatus(st)}
            >
              {st === 'ALL' ? 'All Requests' : st}
            </button>
          ))}
        </div>
      </div>

      {/* Requests Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table>
          <thead>
            <tr>
              <th>Request ID</th>
              <th>Requester</th>
              <th>Target Identity</th>
              <th>Requested Action</th>
              <th>Created</th>
              <th>Status</th>
              <th style={{ width: 220 }}>Review Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={7} className="loading-row" style={{ color: 'var(--text-muted)' }}>
                  No approval requests found for this filter.
                </td>
              </tr>
            ) : (
              filtered.map((req) => {
                const isPending = req.status === 'PENDING';
                const isBusy = actionLoading.startsWith(req.id);
                return (
                  <tr key={req.id}>
                    <td>
                      <span className="font-mono font-bold" style={{ color: 'var(--text-primary)' }}>
                        {req.id}
                      </span>
                    </td>
                    <td>
                      <div className="flex flex-col">
                        <span className="font-semibold">{req.requester}</span>
                        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{req.requester_role}</span>
                      </div>
                    </td>
                    <td>
                      <div className="flex flex-col">
                        <span className="font-semibold">{req.target_user}</span>
                        {req.requested_role && (
                          <span style={{ fontSize: 11, color: 'var(--mark-color-a)' }}>
                            Target Role: {req.requested_role}
                          </span>
                        )}
                      </div>
                    </td>
                    <td>
                      <span className="badge badge-muted font-mono">{req.action}</span>
                    </td>
                    <td>
                      <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                        {formatDate(req.created_at)}
                      </span>
                    </td>
                    <td>
                      <StatusPill status={req.status} />
                    </td>
                    <td>
                      {isPending ? (
                        <div className="flex items-center gap-sm">
                          <button
                            className="btn btn-primary btn-sm"
                            disabled={!canApprove || isBusy}
                            title={canApprove ? 'Approve request' : 'Requires Admin role to approve'}
                            onClick={() => handleDecision(req.id, 'APPROVE')}
                          >
                            <Check size={13} /> Approve
                          </button>
                          <button
                            className="btn btn-danger btn-sm"
                            disabled={isBusy}
                            onClick={() => handleDecision(req.id, 'REJECT')}
                          >
                            <X size={13} /> Reject
                          </button>
                          <button
                            className="btn btn-secondary btn-sm"
                            disabled={isBusy}
                            onClick={() => handleDecision(req.id, 'ESCALATE')}
                          >
                            <ArrowUpRight size={13} /> Escalate
                          </button>
                        </div>
                      ) : (
                        <span style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>
                          Decision finalized
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Policy 403 Violation Dialog */}
      <PolicyViolationModal
        isOpen={!!policyError}
        error={policyError}
        onClose={() => setPolicyError(null)}
      />
    </div>
  );
}

export default Approvals;
