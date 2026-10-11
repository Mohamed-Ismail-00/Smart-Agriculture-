/**
 * pages/logs/LogsPage.jsx
 * -----------------------
 * Real user activity logs (admin only).
 * Fetches from /api/v1/activity-logs
 */

import React, { useEffect, useState } from "react";
import { getActivityLogs } from "../../services/api";
import "../Pages.css";

function LogDataCard({ log }) {
  return (
    <div className="data-card">
      <div className="data-card__row">
        <span className="data-card__label">Action</span>
        <span className="data-card__value data-card__value--bold">{log.action}</span>
      </div>
      <div className="data-card__row">
        <span className="data-card__label">User</span>
        <span className="data-card__value">{log.user_id}</span>
      </div>
      <div className="data-card__row">
        <span className="data-card__label">Target</span>
        <span className="data-card__value">
          {log.target_type} {log.target_id ? `#${log.target_id}` : ""}
        </span>
      </div>
      <div className="data-card__row">
        <span className="data-card__label">Time</span>
        <span className="data-card__value">{new Date(log.created_at).toLocaleString()}</span>
      </div>
      {log.details && (
        <div className="data-card__row">
          <span className="data-card__label">Details</span>
          <span className="data-card__value data-card__value--mono">
            {JSON.stringify(log.details)}
          </span>
        </div>
      )}
      <div className="data-card__row">
        <span className="data-card__label">ID</span>
        <span className="data-card__value data-card__value--mono">{log.log_id}</span>
      </div>
    </div>
  );
}

export default function LogsPage() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const res = await getActivityLogs({ limit: 100 });
        if (mounted) {
          setLogs(res.data || []);
        }
      } catch (e) {
        if (mounted) setError(e.message || "Failed to load activity logs");
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, []);

  if (loading) {
    return (
      <div className="anim-fade-in" style={{ padding: "2rem" }}>
        Loading activity logs...
      </div>
    );
  }

  if (error) {
    return (
      <div className="anim-fade-in" style={{ padding: "2rem", color: "red" }}>
        {error} — You must be logged in as admin to view these logs.
      </div>
    );
  }

  return (
    <div className="anim-fade-in">
      <div className="page-header">
        <h1 className="page-header__title">Activity Logs</h1>
        <p className="page-header__subtitle">
          Real user actions (logins, land operations, exports, etc.). Admin only.
        </p>
      </div>

      <div className="card card--no-hover anim-stagger responsive-table-container" style={{ "--stagger-index": 4, padding: 0, overflow: "hidden" }}>
        <table className="logs-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>User</th>
              <th>Action</th>
              <th>Target</th>
              <th>Time</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {logs.length === 0 && (
              <tr>
                <td colSpan={6} style={{ textAlign: "center", padding: "2rem", color: "var(--gray-500)" }}>
                  No activity logs yet.
                </td>
              </tr>
            )}
            {logs.map((log) => (
              <tr key={log.log_id}>
                <td style={{ fontFamily: "monospace", fontSize: "12px" }}>{log.log_id}</td>
                <td>{log.user_id}</td>
                <td style={{ fontWeight: 600 }}>{log.action}</td>
                <td>
                  {log.target_type} {log.target_id ? `#${log.target_id}` : ""}
                </td>
                <td style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                  {new Date(log.created_at).toLocaleString()}
                </td>
                <td style={{ fontSize: "12px", maxWidth: 240, overflow: "hidden", textOverflow: "ellipsis" }}>
                  {log.details ? JSON.stringify(log.details) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="data-card-list">
          {logs.length === 0 ? (
            <div style={{ textAlign: "center", padding: "2rem", color: "var(--gray-500)" }}>
              No activity logs yet.
            </div>
          ) : (
            logs.map((log) => <LogDataCard key={log.log_id} log={log} />)
          )}
        </div>
      </div>

      <p style={{ marginTop: "1rem", fontSize: "12px", color: "var(--gray-500)" }}>
        Only users with role <strong>admin</strong> can access this view.
      </p>
    </div>
  );
}