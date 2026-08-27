import { useState } from 'react';
import { createUser, provisionUser, listGroups, moveUser } from '../api/client';
import RotateMark from '../components/RotateMark';
import { Check, ChevronRight } from 'lucide-react';
import './OnboardOffboard.css';

const STEPS = [
  { index: 0, label: 'Create User',  desc: 'Add the user to Okta' },
  { index: 1, label: 'Provision',    desc: 'Activate the Okta account' },
  { index: 2, label: 'Assign Group', desc: 'Place in the correct group' },
  { index: 3, label: 'Done',         desc: 'Onboarding complete' },
];

function StepIndicator({ current }) {
  return (
    <div className="wizard-steps">
      {STEPS.map((step, i) => (
        <div key={step.index} className="wizard-step">
          <div className={`step-circle ${i < current ? 'done' : i === current ? 'active' : 'pending'}`}>
            {i < current ? <Check size={14} /> : i + 1}
          </div>
          {i < STEPS.length - 1 && (
            <div className={`step-line ${i < current ? 'done' : ''}`} />
          )}
        </div>
      ))}
    </div>
  );
}

function OnboardOffboard() {
  const [step,       setStep]       = useState(0);
  const [loading,    setLoading]    = useState(false);
  const [error,      setError]      = useState('');
  const [createdId,  setCreatedId]  = useState('');
  const [groups,     setGroups]     = useState([]);

  // Form state
  const [form, setForm] = useState({
    firstName: '', lastName: '', email: '', login: '',
    selectedGroup: '', oldGroup: '__none__',
  });
  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  // Step 0: Create user
  const handleCreate = async (e) => {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      const result = await createUser({
        first_name: form.firstName,
        last_name:  form.lastName,
        email:      form.email,
        // Note: backend UserCreate schema only accepts first_name, last_name, email
        // Login is set to email automatically by the Okta client
      });
      const userId = result?.user?.id || result?.id || '';
      setCreatedId(userId);
      setStep(1);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Step 1: Provision
  const handleProvision = async () => {
    setError(''); setLoading(true);
    try {
      await provisionUser(createdId);
      const gs = await listGroups();
      setGroups(gs || []);
      setStep(2);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Assign group
  const handleAssignGroup = async () => {
    setError(''); setLoading(true);
    try {
      await moveUser(createdId, form.oldGroup, form.selectedGroup);
      setStep(3);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setStep(0); setError(''); setCreatedId('');
    setForm({ firstName: '', lastName: '', email: '', login: '', selectedGroup: '', oldGroup: '__none__' });
  };

  return (
    <div>
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="page-title">Onboard / Offboard Wizard</h1>
          <p className="page-subtitle">Sequential identity provisioning and group assignment workflow</p>
        </div>
        <RotateMark size={28} isLoading={loading} />
      </div>

      <div className="wizard-container card">
        <StepIndicator current={step} />

        {error && <div className="error-box" style={{ marginBottom: 20 }}>{error}</div>}

        {/* Step 0: Create */}
        {step === 0 && (
          <form onSubmit={handleCreate} className="wizard-form">
            <h3 className="wizard-step-title">Step 1 — Create User Profile</h3>
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
            <div className="wizard-actions">
              <button type="submit" className="btn btn-primary" disabled={loading}>
                {loading ? 'Creating…' : 'Continue to Provision'} <ChevronRight size={15} />
              </button>
            </div>
          </form>
        )}

        {/* Step 1: Provision */}
        {step === 1 && (
          <div className="wizard-form">
            <h3 className="wizard-step-title">Step 2 — Provision Account</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 16 }}>
              User registered with Okta ID: <code style={{ fontFamily: 'var(--font-mono)', color: 'var(--mark-color-a)', fontWeight: 600 }}>{createdId || '(id pending)'}</code>
            </p>
            <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 24 }}>
              Click below to activate and provision the user account in Okta.
            </p>
            <div className="wizard-actions">
              <button className="btn btn-primary" onClick={handleProvision} disabled={loading}>
                {loading ? 'Provisioning…' : 'Provision Account'} <ChevronRight size={15} />
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Assign Group */}
        {step === 2 && (
          <div className="wizard-form">
            <h3 className="wizard-step-title">Step 3 — Assign Group</h3>
            <div className="form-group">
              <label className="form-label">Target Group *</label>
              <select required value={form.selectedGroup} onChange={set('selectedGroup')}>
                <option value="">Select a group…</option>
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>{g.profile?.name || g.id}</option>
                ))}
              </select>
            </div>
            <div className="wizard-actions">
              <button className="btn btn-primary" onClick={handleAssignGroup} disabled={loading || !form.selectedGroup}>
                {loading ? 'Assigning…' : 'Assign & Finish'} <ChevronRight size={15} />
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Done */}
        {step === 3 && (
          <div className="wizard-done">
            <div className="wizard-done-icon">
              <Check size={32} color="var(--status-success)" />
            </div>
            <h3 className="wizard-step-title" style={{ textAlign: 'center' }}>Onboarding Complete</h3>
            <p style={{ color: 'var(--text-secondary)', textAlign: 'center', fontSize: 14, marginBottom: 24 }}>
              The user profile has been created, provisioned, and assigned to the specified access group.
            </p>
            <div className="wizard-actions" style={{ justifyContent: 'center' }}>
              <button className="btn btn-secondary" onClick={reset}>Onboard Another User</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default OnboardOffboard;
