import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { loginWithEmail } from '../api/client';
import RotateMark from '../components/RotateMark';
import { Mail, ArrowRight, ShieldCheck, AlertCircle } from 'lucide-react';
import './Login.css';

function Login() {
  const navigate = useNavigate();
  const [email, setEmail]       = useState('');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    const cleanEmail = email.trim();
    if (!cleanEmail) {
      setError('Please enter a valid email address.');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await loginWithEmail(cleanEmail);
      navigate('/dashboard');
    } catch (err) {
      setError(err.message || 'Authentication failed. Please verify your email.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card card">
        {/* Brand Header */}
        <div className="login-brand">
          <RotateMark size={44} isLoading={loading} />
          <h1 className="login-title">IntelliID</h1>
          <p className="login-subtitle">
            Identity Lifecycle & Policy Governance
          </p>
        </div>

        {/* Info pill */}
        <div className="login-info-pill">
          <ShieldCheck size={14} color="var(--mark-color-a)" />
          <span>Okta Directory Authentication</span>
        </div>

        {/* Error notification */}
        {error && (
          <div className="error-box login-error">
            <AlertCircle size={15} style={{ flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}

        {/* Email-only Login Form */}
        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label className="form-label" htmlFor="email-input">
              Okta Identity Email
            </label>
            <div className="login-input-wrap">
              <Mail size={16} className="login-input-icon" />
              <input
                id="email-input"
                type="email"
                required
                autoFocus
                placeholder="name@corp.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loading}
                className="login-input"
              />
            </div>
            <span className="login-hint">
              Enter your registered Okta directory email to authenticate.
            </span>
          </div>

          <button
            type="submit"
            className="btn btn-primary login-btn"
            disabled={loading}
          >
            <span>{loading ? 'Authenticating…' : 'Sign In with Okta'}</span>
            <ArrowRight size={16} />
          </button>
        </form>

        <div className="login-footer">
          <span>Protected by 7-Policy RBAC Governance Engine</span>
        </div>
      </div>
    </div>
  );
}

export default Login;
