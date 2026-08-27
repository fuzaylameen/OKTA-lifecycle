import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import RotateMark from '../components/RotateMark';
import './Login.css';

function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    // Simulate a brief "auth" delay, then navigate — non-functional as per spec
    await new Promise((r) => setTimeout(r, 1000));
    setLoading(false);
    navigate('/dashboard');
  };

  return (
    <div className="login-page">
      {/* Background orbs */}
      <div className="login-orb login-orb-a" />
      <div className="login-orb login-orb-b" />

      <div className="login-card">
        {/* Hero mark */}
        <div className="login-mark-wrap">
          <RotateMark size={120} isLoading={loading} />
        </div>

        {/* Brand */}
        <h1 className="login-brand">IntelliID</h1>
        <p className="login-tagline">Intelligent Identity Lifecycle Orchestrator</p>

        {/* Form */}
        <form className="login-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="login-email">Email</label>
            <input
              id="login-email"
              type="email"
              placeholder="admin@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="login-password">Password</label>
            <input
              id="login-password"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary login-submit"
            disabled={loading}
          >
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        <p className="login-footer">
          IntelliID v1.0 · Powered by Okta
        </p>
      </div>
    </div>
  );
}

export default Login;
