import { useEffect, useState } from 'react';
import { listLogs } from '../api/client';
import RotateMark from '../components/RotateMark';
import {
  FileText, Search, RefreshCw, Filter,
  ChevronDown, ChevronUp, X, Shield,
  CheckCircle2, XCircle, AlertCircle, Eye
} from 'lucide-react';
import './AuditLog.css';

// ── Helpers ───────────────────────────────────────────────────────────────────

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

// Derive a display decision from log status and action
function deriveDecision(log) {
  if (log.decision) return log.decision.toUpperCase();
  const s = log.status?.toUpperCase();
  if (s === 'SUCCESS') return 'ALLOWED';
  if (s === 'FAILED')  return 'DENIED';
  return s || 'UNKNOWN';
}

// Derive policy from message or new_value if present
function derivePolicy(log) {
  if (log.policy) return log.policy;
  const msg = log.message || '';
  // Extract policy name if embedded in message
  const match = msg.match(/Policy:\s*(\w+Policy)/);
  if (match) return match[1];
  return null;
}

// Derive role from email heuristic
function deriveRole(log) {
  if (log.requester_role) return log.requester_role;
  const email = (log.user_email || '').toLowerCase();
  if (email.includes('admin'))   return 'Admin';
  if (email.includes('manager')) return 'Manager';
  if (email.includes('audit'))   return 'Auditor';
  if (email.includes('role'))    return 'RoleManager';
  return 'Manager';
}

function DecisionBadge({ decision }) {
  const d = decision?.toUpperCase();
  if (d === 'ALLOWED' || d === 'SUCCESS')
    return <span className="badge badge-success"><CheckCircle2 size={11} /> {d}</span>;
  if (d === 'DENIED' || d === 'FAILED')
    return <span className="badge badge-danger"><XCircle size={11} /> {d}</span>;
  return <span className="badge badge-muted">{d}</span>;
}

// ── Row Detail Modal ──────────────────────────────────────────────────────────

function LogDetailModal({ log, onClose }) {
  if (!log) return null;
  const fields = [
    { label: 'Audit Log ID',  val: log.id },
    { label: 'Action',        val: log.action },
    { label: 'User Email',    val: log.user_email || '—' },
    { label: 'User ID',       val: log.user_id || '—' },
    { label: 'Status',        val: log.status },
    { label: 'Decision',      val: deriveDecision(log) },
    { label: 'Policy',        val: derivePolicy(log) || 'N/A' },
    { label: 'Old Value',     val: log.old_value || 'N/A' },
    { label: 'New Value',     val: log.new_value || 'N/A' },
    { label: 'Message',       val: log.message || '—' },
    { label: 'Timestamp',     val: formatDate(log.created_at) },
  ];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 560 }}>
        <div className="modal-header">
          <div>
            <h3 className="modal-title">Audit Event Detail</h3>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
              Authorization & lifecycle decision record
            </p>
          </div>
          <button className="btn-icon" onClick={onClose}><X size={16} /></button>
        </div>

        <div className="log-detail-grid">
          {fields.map(({ label, val }) => (
            <div key={label} className="log-detail-item">
              <span className="log-detail-label">{label}</span>
              <span className="log-detail-val">{val}</span>
            </div>
          ))}
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

// ── Main Audit Log Component ──────────────────────────────────────────────────

function AuditLog() {
  const [logs, setLogs]                   = useState([]);
  const [loading, setLoading]             = useState(true);
  const [error, setError]                 = useState('');
  const [search, setSearch]               = useState('');
  const [filterDecision, setFilterDecision] = useState('ALL');
  const [filterAction, setFilterAction]   = useState('ALL');
  const [sortDir, setSortDir]             = useState('desc');
  const [selectedLog, setSelectedLog]     = useState(null);

  const fetchLogs = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await listLogs();
      setLogs(data || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchLogs(); }, []);

  // Extract unique actions for filter
  const uniqueActions = ['ALL', ...new Set(logs.map((l) => l.action).filter(Boolean))];

  const filtered = logs
    .filter((log) => {
      const q = search.toLowerCase();
      const matchSearch = !q || [
        log.action, log.user_email, log.user_id, log.message, log.status
      ].some((v) => v?.toLowerCase().includes(q));

      const decision = deriveDecision(log);
      const matchDecision = filterDecision === 'ALL' || decision === filterDecision;
      const matchAction   = filterAction   === 'ALL' || log.action === filterAction;
      return matchSearch && matchDecision && matchAction;
    })
    .sort((a, b) => {
      const ta = new Date(a.created_at).getTime();
      const tb = new Date(b.created_at).getTime();
      return sortDir === 'desc' ? tb - ta : ta - tb;
    });

  return (
    <div className="audit-page">
      {/* Header */}
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="page-title">Audit Log</h1>
          <p className="page-subtitle">
            {loading ? 'Loading records…' : `${filtered.length} of ${logs.length} authorization events`}
          </p>
        </div>
        <div className="flex items-center gap-sm">
          <RotateMark size={28} isLoading={loading} />
          <button className="btn btn-secondary btn-sm" onClick={fetchLogs} title="Refresh">
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* Filter Row */}
      <div className="flex items-center gap-md" style={{ marginBottom: 16, flexWrap: 'wrap' }}>
        <div className="search-box" style={{ width: 280 }}>
          <Search size={15} className="search-icon" />
          <input
            placeholder="Search action, user, message…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div className="flex items-center gap-sm">
          <select
            value={filterDecision}
            onChange={(e) => setFilterDecision(e.target.value)}
            style={{ height: 36, borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)',
                     background: 'var(--bg-panel)', color: 'var(--text-primary)', padding: '0 10px', fontSize: 13 }}
          >
            <option value="ALL">All Decisions</option>
            <option value="ALLOWED">ALLOWED</option>
            <option value="DENIED">DENIED</option>
          </select>

          <select
            value={filterAction}
            onChange={(e) => setFilterAction(e.target.value)}
            style={{ height: 36, borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)',
                     background: 'var(--bg-panel)', color: 'var(--text-primary)', padding: '0 10px', fontSize: 13 }}
          >
            {uniqueActions.map((a) => (
              <option key={a} value={a}>{a === 'ALL' ? 'All Actions' : a}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Error */}
      {error && <div className="error-box" style={{ marginBottom: 16 }}>⚠ {error}</div>}

      {/* Columns: Timestamp | Requester | Role | Action | Target | Decision | Policy | Reason */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table>
          <thead>
            <tr>
              <th
                style={{ cursor: 'pointer', userSelect: 'none' }}
                onClick={() => setSortDir((d) => d === 'desc' ? 'asc' : 'desc')}
              >
                <div className="flex items-center gap-sm">
                  Timestamp
                  {sortDir === 'desc' ? <ChevronDown size={12} /> : <ChevronUp size={12} />}
                </div>
              </th>
              <th>Requester</th>
              <th>Role</th>
              <th>Action</th>
              <th>Decision</th>
              <th>Policy</th>
              <th>Reason</th>
              <th style={{ width: 50 }}></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 5 }, (_, i) => (
                <tr key={i} className="skeleton-row">
                  {Array.from({ length: 8 }, (_, j) => (
                    <td key={j} style={{ padding: '14px 16px' }}>
                      <div className="skeleton" style={{ height: 13, borderRadius: 4, width: j === 6 ? '80%' : '60%' }} />
                    </td>
                  ))}
                </tr>
              ))
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={8} className="loading-row" style={{ color: 'var(--text-muted)' }}>
                  No audit records match the current filters.
                </td>
              </tr>
            ) : (
              filtered.map((log, idx) => {
                const decision = deriveDecision(log);
                const policy = derivePolicy(log);
                const role = deriveRole(log);
                return (
                  <tr
                    key={log.id}
                    className="audit-log-row"
                    style={{ '--row-delay': `${Math.min(idx * 15, 200)}ms`, cursor: 'pointer' }}
                    onClick={() => setSelectedLog(log)}
                  >
                    <td style={{ fontSize: 12, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                      {formatDate(log.created_at)}
                    </td>
                    <td style={{ fontSize: 13 }}>
                      <span className="font-mono">{log.user_email || log.user_id || '—'}</span>
                    </td>
                    <td>
                      <span className="badge badge-muted" style={{ fontSize: 10.5 }}>{role}</span>
                    </td>
                    <td>
                      <span className="font-bold" style={{ fontSize: 13, color: 'var(--text-primary)' }}>
                        {log.action}
                      </span>
                    </td>
                    <td><DecisionBadge decision={decision} /></td>
                    <td style={{ fontSize: 11.5 }}>
                      {policy ? (
                        <span className="font-mono policy-chip">{policy}</span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>—</span>
                      )}
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--text-secondary)', maxWidth: 220 }}>
                      <span className="truncate-text">{log.message || '—'}</span>
                    </td>
                    <td>
                      <button className="btn-icon" title="View full detail" onClick={() => setSelectedLog(log)}>
                        <Eye size={14} />
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Detail Modal */}
      {selectedLog && (
        <LogDetailModal log={selectedLog} onClose={() => setSelectedLog(null)} />
      )}
    </div>
  );
}

export default AuditLog;
