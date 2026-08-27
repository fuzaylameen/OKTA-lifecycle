import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import Users from './pages/Users';
import UserDetails from './pages/UserDetails';
import Groups from './pages/Groups';
import LifecycleExecution from './pages/LifecycleExecution';
import Approvals from './pages/Approvals';
import Governance from './pages/Governance';
import AuditLog from './pages/AuditLog';
import OnboardOffboard from './pages/OnboardOffboard';
import './index.css';

// Layout wrapper for authenticated pages (top navbar + content)
function AppLayout({ children }) {
  return (
    <div className="page-layout">
      <Navbar />
      <main className="main-content">
        {children}
      </main>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Root redirect to Dashboard */}
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/login" element={<Navigate to="/dashboard" replace />} />

        {/* Core application routes */}
        <Route path="/dashboard"   element={<AppLayout><Dashboard /></AppLayout>} />
        <Route path="/users"       element={<AppLayout><Users /></AppLayout>} />
        <Route path="/users/:id"   element={<AppLayout><UserDetails /></AppLayout>} />
        <Route path="/groups"      element={<AppLayout><Groups /></AppLayout>} />
        <Route path="/lifecycle"   element={<AppLayout><LifecycleExecution /></AppLayout>} />
        <Route path="/approvals"   element={<AppLayout><Approvals /></AppLayout>} />
        <Route path="/governance"  element={<AppLayout><Governance /></AppLayout>} />
        <Route path="/audit"       element={<AppLayout><AuditLog /></AppLayout>} />
        <Route path="/onboard"     element={<AppLayout><OnboardOffboard /></AppLayout>} />

        {/* 404 fallback */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
