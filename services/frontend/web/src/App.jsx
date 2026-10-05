/**
 * App.jsx
 * -------
 * Root component with routing and auth protection.
 */

import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { NotificationProvider } from "./context/NotificationContext";
import { ConfirmProvider } from "./context/ConfirmContext";

// Public Pages
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";

// Layout
import AppLayout from "./components/layout/AppLayout";

// Protected Pages
import DashboardPage from "./pages/DashboardPage";
import LandsPage from "./pages/lands/LandsPage";
import AddLandPage from "./pages/lands/AddLandPage";
import LandDetailsPage from "./pages/lands/LandDetailsPage";
import CompareLandsPage from "./pages/compare/CompareLandsPage";
import MethodologyPage from "./pages/methodology/MethodologyPage";
import AboutPage from "./pages/about/AboutPage";
import ProfilePage from "./pages/profile/ProfilePage";
import LogsPage from "./pages/logs/LogsPage";

/**
 * ProtectedRoute — redirects to /login if user is not authenticated.
 * Wraps content in the global AppLayout.
 */
function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        fontFamily: "var(--font-sans)",
        color: "#6b7280",
      }}>
        Loading...
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <AppLayout>{children}</AppLayout>;
}

/**
 * PublicRoute — redirects to /dashboard if user is already authenticated.
 */
function PublicRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) return null;

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
}

function AppRoutes() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={
        <PublicRoute><LoginPage /></PublicRoute>
      } />
      <Route path="/register" element={
        <PublicRoute><RegisterPage /></PublicRoute>
      } />

      {/* Protected routes */}
      <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
      <Route path="/lands" element={<ProtectedRoute><LandsPage /></ProtectedRoute>} />
      <Route path="/lands/new" element={<ProtectedRoute><AddLandPage /></ProtectedRoute>} />
      <Route path="/lands/:id" element={<ProtectedRoute><LandDetailsPage /></ProtectedRoute>} />
      <Route path="/lands/compare" element={<ProtectedRoute><CompareLandsPage /></ProtectedRoute>} />
      <Route path="/methodology" element={<ProtectedRoute><MethodologyPage /></ProtectedRoute>} />
      <Route path="/about" element={<ProtectedRoute><AboutPage /></ProtectedRoute>} />
      <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
      <Route path="/logs" element={<ProtectedRoute><LogsPage /></ProtectedRoute>} />

      {/* Default redirect */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <NotificationProvider>
          <ConfirmProvider>
            <AppRoutes />
          </ConfirmProvider>
        </NotificationProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;