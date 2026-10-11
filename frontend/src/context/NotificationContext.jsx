/**
 * context/NotificationContext.jsx
 * -------------------------------
 * Robust notification system with:
 * - Real-time polling: polls /notifications/unread-count every 30s
 *   and fetches full list when count changes.
 * - Unread badge: exposes `unreadCount` for the topbar bell.
 * - Mark-as-read: exposes `markRead(id)` and `markAllRead()` actions.
 * - Server-merge: deduplicates server + UI-origin notifications.
 * - Stops polling when the tab is hidden (Page Visibility API).
 */

import { createContext, useContext, useState, useCallback, useEffect, useRef } from "react";
import {
  listNotifications,
  getUnreadNotificationCount,
  markNotificationRead,
  markAllNotificationsRead,
} from "../services/api";
import { useAuth } from "./AuthContext";

const NotificationContext = createContext(null);

const POLL_INTERVAL_MS = 30_000; // 30 seconds
const MAX_NOTIFICATIONS = 30;

export function NotificationProvider({ children }) {
  const { user } = useAuth();
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const lastKnownUnread = useRef(0);
  const pollTimerRef = useRef(null);

  // ---------------------------------------------------------------------------
  // Add a UI-originated notification (from local actions like form submission)
  // ---------------------------------------------------------------------------
  const addNotification = useCallback((notif) => {
    const item = {
      id: `ui-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      timestamp: new Date().toISOString(),
      alert_type: notif.type || notif.alert_type || "ui_message",
      severity: notif.severity || "medium",
      message: notif.message || notif.text || "Notification",
      land_id: notif.land_id || notif.landId || null,
      is_read: false,
      source: "ui",
      ...notif,
    };
    setNotifications((prev) => [item, ...prev].slice(0, MAX_NOTIFICATIONS));
    setUnreadCount((prev) => prev + 1);
  }, []);

  // ---------------------------------------------------------------------------
  // Load full notification list from server and merge with UI ones
  // ---------------------------------------------------------------------------
  const loadServerNotifications = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const res = await listNotifications(20);
      const serverItems = (res?.data || []).map((a) => ({
        ...a,
        source: "server",
      }));

      // Update unread count from server response
      if (typeof res?.unread_count === "number") {
        setUnreadCount(res.unread_count);
        lastKnownUnread.current = res.unread_count;
      }

      setNotifications((prev) => {
        const uiOnes = prev.filter((p) => p.source === "ui");
        const merged = [...serverItems, ...uiOnes];
        const seen = new Set();
        const unique = [];
        for (const m of merged) {
          const key = m.id || `${m.land_id}-${m.timestamp}`;
          if (!seen.has(key)) {
            seen.add(key);
            unique.push(m);
          }
        }
        return unique.slice(0, MAX_NOTIFICATIONS);
      });
    } catch {
      // Non-fatal: keep existing notifications
    } finally {
      setLoading(false);
    }
  }, [user]);

  // ---------------------------------------------------------------------------
  // Fast poll: only checks unread count; fetches full list on change
  // ---------------------------------------------------------------------------
  const pollUnreadCount = useCallback(async () => {
    if (!user) return;
    try {
      const res = await getUnreadNotificationCount();
      const newCount = res?.unread_count ?? 0;
      if (newCount !== lastKnownUnread.current) {
        lastKnownUnread.current = newCount;
        setUnreadCount(newCount);
        // Fetch full list so new notifications appear
        loadServerNotifications();
      }
    } catch {
      // Silently ignore poll errors
    }
  }, [user, loadServerNotifications]);

  // ---------------------------------------------------------------------------
  // Start/stop polling based on auth + tab visibility
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!user) return;

    // Initial load
    loadServerNotifications();

    // Start polling
    const startPolling = () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      pollTimerRef.current = setInterval(pollUnreadCount, POLL_INTERVAL_MS);
    };

    const stopPolling = () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };

    startPolling();

    // Pause when tab is hidden, resume when visible
    const handleVisibility = () => {
      if (document.hidden) {
        stopPolling();
      } else {
        pollUnreadCount(); // Immediate catch-up check
        startPolling();
      }
    };

    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      stopPolling();
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [user, loadServerNotifications, pollUnreadCount]);

  // ---------------------------------------------------------------------------
  // Mark a single notification as read
  // ---------------------------------------------------------------------------
  const markRead = useCallback(async (id) => {
    // Optimistic update
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
    );
    setUnreadCount((prev) => Math.max(0, prev - 1));

    // Server sync (only for server-origin notifications with numeric IDs)
    if (typeof id === "number") {
      try {
        await markNotificationRead(id);
      } catch {
        // Non-fatal: badge will correct on next poll
      }
    }
  }, []);

  // ---------------------------------------------------------------------------
  // Mark all notifications as read
  // ---------------------------------------------------------------------------
  const markAllRead = useCallback(async () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    setUnreadCount(0);
    lastKnownUnread.current = 0;

    try {
      await markAllNotificationsRead();
    } catch {
      // Non-fatal
    }
  }, []);

  // ---------------------------------------------------------------------------
  // Remove a notification from local state
  // ---------------------------------------------------------------------------
  const removeNotification = useCallback((id) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const clearAll = useCallback(() => {
    setNotifications([]);
    setUnreadCount(0);
    lastKnownUnread.current = 0;
  }, []);

  const value = {
    notifications,
    unreadCount,
    loading,
    addNotification,
    loadServerNotifications,
    markRead,
    markAllRead,
    clearAll,
    removeNotification,
  };

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotifications() {
  const ctx = useContext(NotificationContext);
  if (!ctx) {
    return {
      notifications: [],
      unreadCount: 0,
      loading: false,
      addNotification: () => {},
      loadServerNotifications: async () => {},
      markRead: async () => {},
      markAllRead: async () => {},
      clearAll: () => {},
      removeNotification: () => {},
    };
  }
  return ctx;
}

export default NotificationContext;
