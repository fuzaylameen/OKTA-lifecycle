import { ShieldAlert, X } from 'lucide-react';
import './PolicyViolationModal.css';

/**
 * PolicyViolationModal
 *
 * Displays a structured Policy Engine block dialog when the backend returns
 * an HTTP 403 policy rejection or authorization failure.
 */
function PolicyViolationModal({ isOpen, error, onClose }) {
  if (!isOpen || !error) return null;

  const policyName = error.policy || 'Access Control Policy';
  const reasonText = error.reason || error.message || 'Operation denied by policy engine.';

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal policy-modal" onClick={(e) => e.stopPropagation()}>
        <div className="policy-modal-header">
          <div className="policy-modal-badge">
            <ShieldAlert size={20} color="var(--status-danger)" />
            <span>Action Blocked</span>
          </div>
          <button className="btn-icon" onClick={onClose} aria-label="Close dialog">
            <X size={16} />
          </button>
        </div>

        <div className="policy-modal-body">
          <div className="policy-item">
            <span className="policy-item-label">Violated Policy</span>
            <span className="policy-item-value policy-name">{policyName}</span>
          </div>

          <div className="policy-item">
            <span className="policy-item-label">Enforcement Reason</span>
            <p className="policy-item-reason">{reasonText}</p>
          </div>
        </div>

        <div className="modal-footer" style={{ borderTop: '1px solid var(--border-subtle)' }}>
          <button className="btn btn-secondary" onClick={onClose}>
            Acknowledge
          </button>
        </div>
      </div>
    </div>
  );
}

export default PolicyViolationModal;
