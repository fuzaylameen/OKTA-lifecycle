import { useState, useEffect } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import RotateMark from './RotateMark';
import { getCurrentUser, logout } from '../api/client';
import {
  LayoutDashboard, Users, ShieldCheck, FileText,
  UserCheck, AlertTriangle, LogOut, User
} from 'lucide-react';
import './Navbar.css';

const NAV_ITEMS = [
  { to: '/dashboard',  icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/users',      icon: Users,           label: 'Users' },
  { to: '/groups',     icon: ShieldCheck,     label: 'Access & Groups' },
  { to: '/governance', icon: AlertTriangle,   label: 'Governance' },
  { to: '/audit',      icon: FileText,        label: 'Audit Log' },
  { to: '/onboard',    icon: UserCheck,       label: 'Onboard Wizard' },
];

function Navbar() {
  const navigate = useNavigate();
  const [currentUser, setCurrentUser] = useState(null);

  useEffect(() => {
    getCurrentUser().then(setCurrentUser);
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="top-navbar-wrapper">
      <nav className="top-navbar-pill">
        {/* Left: Brand */}
        <NavLink to="/dashboard" className="nav-brand">
          <RotateMark size={32} />
          <span className="nav-brand-name">IntelliID</span>
        </NavLink>

        {/* Center: Navigation Links */}
        <div className="nav-links">
          {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            >
              <Icon size={17} strokeWidth={2.1} />
              <span>{label}</span>
            </NavLink>
          ))}
        </div>

        {/* Right: User Profile & Logout */}
        <div className="nav-right">
          {currentUser && (
            <div className="nav-user-badge" title={currentUser.email}>
              <User size={13} />
              <span className="nav-user-role">{currentUser.role || 'User'}</span>
            </div>
          )}
          <button
            className="btn-icon nav-logout-btn"
            onClick={handleLogout}
            title="Sign out"
            aria-label="Sign out"
          >
            <LogOut size={15} />
          </button>
        </div>
      </nav>
    </header>
  );
}

export default Navbar;
