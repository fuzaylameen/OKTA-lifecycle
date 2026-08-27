import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Navbar from './components/Navbar';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Users from './pages/Users';
import UserDetails from './pages/UserDetails';
import Groups from './pages/Groups';
import Governance from './pages/Governance';
import AuditLog from './pages/AuditLog';
import OnboardOffboard from './pages/OnboardOffboard';
import { getAuthToken } from './api/client';
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

// Protected route wrapper: if user isn't logged in, send them to /login
function ProtectedRoute({ children }) {
  const token = getAuthToken();
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <AppLayout>{children}</AppLayout>;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public Login Route */}
        <Route path="/login" element={<Login />} />

        {/* Root redirect: check token */}
        <Route
          path="/"
          element={<Navigate to={getAuthToken() ? '/dashboard' : '/login'} replace />}
        />

        {/* Protected application routes */}
        <Route path="/dashboard"   element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
        <Route path="/users"       element={<ProtectedRoute><Users /></ProtectedRoute>} />
        <Route path="/users/:id"   element={<ProtectedRoute><UserDetails /></ProtectedRoute>} />
        <Route path="/groups"      element={<ProtectedRoute><Groups /></ProtectedRoute>} />
        <Route path="/governance"  element={<ProtectedRoute><Governance /></ProtectedRoute>} />
        <Route path="/audit"       element={<ProtectedRoute><AuditLog /></ProtectedRoute>} />
        <Route path="/onboard"     element={<ProtectedRoute><OnboardOffboard /></ProtectedRoute>} />

        {/* 404 fallback */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
