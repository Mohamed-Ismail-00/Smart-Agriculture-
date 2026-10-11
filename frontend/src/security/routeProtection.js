/**
 * routeProtection.js
 * ------------------
 * React route guards and hooks for protected pages.
 *
 * Example:
 *   <Route path="/lands/:publicId" element={<ProtectedRoute><LandDetails /></ProtectedRoute>} />
 */

import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <div style={{ padding: 40, textAlign: 'center' }}>Checking authentication...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}

export function useRequireAuth() {
  const { isAuthenticated, loading } = useAuth();
  return { isAuthenticated, loading };
}
