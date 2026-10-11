/* eslint-disable react-refresh/only-export-components */
/**
 * context/AuthContext.jsx
 * -----------------------
 * Global authentication state using React Context.
 *
 * Provides:
 * - user object (null if not logged in)
 * - login / register / logout functions
 * - loading state
 * - isAuthenticated boolean
 */

// Force full reload on HMR for this file to avoid "useAuth export is incompatible" Fast Refresh issues
// @refresh reset

import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { loginUser, registerUser, logoutUser, getMe, getToken, clearToken, setTokens, googleLogin } from "../services/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(() => Boolean(getToken()));
  const [error, setError] = useState(null);

  // On mount: check if we have a stored token and load user
  useEffect(() => {
    const token = getToken();
    if (token) {
      getMe()
        .then((res) => setUser(res.data))
        .catch(() => {
          clearToken();
          setUser(null);
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = useCallback(async (email, password) => {
    setError(null);
    await loginUser({ email, password });
    // Fetch user profile immediately to return it
    const meRes = await getMe();
    setUser(meRes.data);
    return meRes.data;
  }, []);

  const register = useCallback(async (email, password, role = "viewer") => {
    setError(null);
    const res = await registerUser({ email, password, role });
    return res;
  }, []);

  const googleSignIn = useCallback(async (credential) => {
    setError(null);
    await googleLogin(credential);
    const meRes = await getMe();
    setUser(meRes.data);
    return meRes.data;
  }, []);

  const logout = useCallback(async () => {
    await logoutUser();
    setUser(null);
  }, []);

  const value = {
    user,
    loading,
    error,
    isAuthenticated: !!user || !!getToken(),
    login,
    register,
    googleSignIn,
    logout,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
