import { NavLink } from 'react-router-dom';
import RotateMark from './RotateMark';
import {
  LayoutDashboard, Users, ShieldCheck, FileText,
  UserCheck, AlertTriangle, PlayCircle, CheckSquare
} from 'lucide-react';
import './Navbar.css';

const NAV_ITEMS = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/users',     icon: Users,           label: 'Users' },
  { to: '/groups',    icon: ShieldCheck,     label: 'Access & Groups' },
  { to: '/lifecycle', icon: PlayCircle,      label: 'Lifecycle' },
  { to: '/approvals', icon: CheckSquare,     label: 'Approvals' },
  { to: '/governance',icon: AlertTriangle,   label: 'Governance' },
  { to: '/audit',     icon: FileText,        label: 'Audit Log' },
  { to: '/onboard',   icon: UserCheck,       label: 'Onboard Wizard' },
];

function Navbar() {
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

        {/* Right: Live Status Badge */}
        <div className="nav-right">
          <div className="status-pill">
            <span className="status-pulse-dot" />
            <span className="status-pill-text">Okta Engine</span>
          </div>
        </div>
      </nav>
    </header>
  );
}

export default Navbar;
