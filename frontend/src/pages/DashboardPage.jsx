/**
 * pages/DashboardPage.jsx — Home dashboard
 */

import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useBreakpoint } from "../hooks/useBreakpoint";
import { useDashboard } from "../hooks/useDashboard";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";
import NDVIChart from "../components/charts/NDVIChart";
import "./Dashboard.css";
import "./mobile-home.css";

function landStatusClass(status) {
  if (!status) return "info";
  const s = status.toLowerCase();
  if (s === "ready" || s === "active" || s === "active_partial" || s === "completed") return "ready";
  if (s === "error" || s === "failed") return "error";
  if (s === "processing") return "processing";
  return "info";
}

function ChevronRight() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { isDrawer, isMobile } = useBreakpoint();
  const isMobileLayout = isDrawer;
  const {
    lands,
    ndviData,
    loading,
    aiInsights,
    aiLoading,
    aiError,
    analyzingLandId,
    preferredLandId,
    stats,
    triggerAnalysis,
  } = useDashboard();

  const firstName = user?.email?.split("@")[0] || "Farmer";

  if (loading) {
    return (
      <div className="anim-fade-in dashboard-page">
        <div className="premium-hero dashboard-hero dashboard-hero--mobile">
          <h1 className="page-header__title">Welcome back</h1>
          <p className="page-header__subtitle">Loading your dashboard...</p>
        </div>
        <div className="dashboard-stats">
          {[0, 1, 2, 3].map((i) => (
            <div className="skeleton dashboard-stat" key={i} style={{ height: 88 }} />
          ))}
        </div>
      </div>
    );
  }

  const otherCount = Math.max(
    0,
    lands.length - stats.readyCount - stats.processingCount - stats.errorCount
  );

  const pieData = [
    { name: "Active", value: stats.readyCount, color: "var(--green-500)" },
    { name: "Processing", value: stats.processingCount, color: "var(--info)" },
    { name: "Error", value: stats.errorCount, color: "var(--error)" },
    { name: "Other", value: otherCount, color: "var(--gray-400)" },
  ].filter((d) => d.value > 0);

  const recentLands = lands.slice(0, isMobileLayout ? 8 : 6);

  return (
    <div className="anim-fade-in dashboard-page">
      <div className={`premium-hero dashboard-hero${isMobileLayout ? " dashboard-hero--mobile" : ""}`}>
        <h1 className="page-header__title dashboard-hero__title">
          Welcome, {firstName} 👋
        </h1>
        <p className="page-header__subtitle dashboard-hero__subtitle">
          Intelligence from {lands.length} registered land{lands.length !== 1 ? "s" : ""}.
        </p>
      </div>

      {isMobileLayout && (
        <div className="dashboard-quick-actions anim-stagger" style={{ "--stagger-index": 0 }}>
          <button type="button" className="dashboard-quick-action" onClick={() => navigate("/lands")}>
            <span className="dashboard-quick-action__icon dashboard-quick-action__icon--green">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M3 6l9-4 9 4" />
                <path d="M3 6v12l9 4 9-4V6" />
              </svg>
            </span>
            My Lands
          </button>
          <button type="button" className="dashboard-quick-action" onClick={() => navigate("/lands/new")}>
            <span className="dashboard-quick-action__icon dashboard-quick-action__icon--blue">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
            </span>
            Add Land
          </button>
          <button type="button" className="dashboard-quick-action" onClick={() => navigate("/lands/compare")}>
            <span className="dashboard-quick-action__icon dashboard-quick-action__icon--purple">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M10 3H5a2 2 0 00-2 2v14a2 2 0 002 2h5" />
                <path d="M14 3h5a2 2 0 012 2v14a2 2 0 01-2 2h-5" />
                <path d="M12 3v18" />
              </svg>
            </span>
            Compare
          </button>
        </div>
      )}

      {stats.processingCount > 0 && (
        <div className="alert alert--warning">
          {stats.processingCount} land{stats.processingCount !== 1 ? "s are" : " is"} still processing.
        </div>
      )}

      <div className="dashboard-stats anim-stagger" style={{ "--stagger-index": 1 }}>
        <div
          className="dashboard-stat dashboard-stat--clickable"
          onClick={() => navigate("/lands")}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === "Enter" && navigate("/lands")}
        >
          <div className="dashboard-stat__icon" style={{ background: "var(--green-50)", color: "var(--green-600)" }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 6l9-4 9 4" />
              <path d="M3 6v12l9 4 9-4V6" />
            </svg>
          </div>
          <div className="dashboard-stat__value" style={{ color: "var(--green-600)" }}>{lands.length}</div>
          <div className="dashboard-stat__label">Total Lands</div>
        </div>
        <div className="dashboard-stat">
          <div className="dashboard-stat__icon" style={{ background: "var(--info-light)", color: "var(--info)" }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <path d="M3 9h18M9 3v18" />
            </svg>
          </div>
          <div className="dashboard-stat__value" style={{ color: "var(--info)" }}>{stats.totalArea.toFixed(1)}</div>
          <div className="dashboard-stat__label">Hectares</div>
        </div>
        <div className="dashboard-stat">
          <div className="dashboard-stat__icon" style={{ background: "var(--warning-light)", color: "var(--amber-500)" }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
            </svg>
          </div>
          <div className="dashboard-stat__value" style={{ color: "var(--amber-500)" }}>
            {stats.latestNDVI !== null ? stats.latestNDVI.toFixed(2) : "—"}
          </div>
          <div className="dashboard-stat__label">Latest NDVI</div>
        </div>
        <div className="dashboard-stat">
          <div className="dashboard-stat__icon" style={{ background: "var(--green-50)", color: "var(--green-600)" }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 11.08V12a10 10 0 11-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
          </div>
          <div className="dashboard-stat__value" style={{ color: "var(--green-600)" }}>
            {stats.readyCount}/{lands.length}
          </div>
          <div className="dashboard-stat__label">Active</div>
        </div>
      </div>

      <div className="dashboard-split anim-stagger" style={{ "--stagger-index": 2 }}>
        <div className="dashboard-chart-card card--no-hover dashboard-chart-card--ndvi">
          <div className="dashboard-chart-card__header">
            <h2 className="dashboard-chart-card__title">NDVI Vegetation Index</h2>
            <span className="badge badge--info">{ndviData.length} obs</span>
          </div>
          <div className="dashboard-chart-card__chart dashboard-chart-card__chart--ndvi">
            {ndviData.length > 0 ? (
              <NDVIChart data={ndviData} compact />
            ) : (
              <div className="dashboard-chart-empty">
                <p className="text-body-sm">No NDVI data available yet.</p>
              </div>
            )}
          </div>
        </div>
        <div className="dashboard-chart-card card--no-hover dashboard-chart-card--pie">
          <div className="dashboard-chart-card__header">
            <h2 className="dashboard-chart-card__title">Lands Breakdown</h2>
          </div>
          <div className="dashboard-chart-card__chart dashboard-chart-card__chart--pie">
            {pieData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy={isMobile ? "46%" : "48%"}
                    innerRadius={isMobile ? 40 : 56}
                    outerRadius={isMobile ? 58 : 76}
                    paddingAngle={4}
                    dataKey="value"
                  >
                    {pieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ borderRadius: "8px", border: "none", boxShadow: "0 4px 12px rgba(0,0,0,0.1)" }} />
                  <Legend verticalAlign="bottom" height={32} iconSize={8} wrapperStyle={{ fontSize: 11, lineHeight: "14px" }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="dashboard-chart-empty">
                <p className="text-body-sm">No land status data yet.</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {preferredLandId && (
        <div className="ai-insights-panel anim-stagger" style={{ "--stagger-index": 3 }}>
          <div className="ai-insights-header">
            <div>
              <span className="ai-badge">✨ AI Agronomist</span>
              <h2 className="section-header__title" style={{ marginTop: "var(--space-sm)" }}>Deep Intelligence</h2>
            </div>
            <button type="button" className="ai-trigger-btn" onClick={triggerAnalysis} disabled={analyzingLandId === preferredLandId}>
              {analyzingLandId === preferredLandId ? "Analyzing..." : "Generate AI Analysis"}
            </button>
          </div>
          {aiLoading ? (
            <div style={{ padding: "var(--space-xl)", textAlign: "center", color: "var(--text-secondary)" }}>Loading AI Insights...</div>
          ) : aiError ? (
            <div className="alert alert--error" style={{ margin: "var(--space-md)", padding: "var(--space-lg)" }}>{aiError}</div>
          ) : aiInsights.length > 0 ? (
            <div className="ai-card-grid">
              {aiInsights.map((insight) => (
                <div key={insight.insight_id} className="ai-insight-card">
                  <div className="ai-insight-title">{insight.title}</div>
                  <div className="ai-insight-body">{insight.body}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state" style={{ padding: "var(--space-xl)" }}>
              <p className="text-body-sm">No AI insights yet. Tap the button above to run an analysis.</p>
            </div>
          )}
        </div>
      )}

      {lands.length > 0 && (
        <div className="anim-stagger" style={{ "--stagger-index": 4 }}>
          <div className="dashboard-section-head">
            <h2 className="dashboard-section-head__title">Your Lands</h2>
            <button type="button" className="btn btn--ghost btn--sm" onClick={() => navigate("/lands")}>
              View All →
            </button>
          </div>

          {/* Tablet: horizontal scroll chips */}
          <div className="dashboard-lands-scroll">
            {recentLands.map((land) => (
              <div
                key={land.land_id}
                className="dashboard-land-chip"
                onClick={() => navigate(`/lands/${land.public_id}`)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && navigate(`/lands/${land.public_id}`)}
              >
                <div className={`dashboard-land-chip__thumb dashboard-land-chip__thumb--${landStatusClass(land.status)}`} />
                <div className="dashboard-land-chip__body">
                  <div className="dashboard-land-chip__name">{land.name}</div>
                  <div className="dashboard-land-chip__meta">
                    {land.area_hectares || "—"} ha · {(land.status || "active").split(":")[0]}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Phone: compact list rows */}
          <div className="dashboard-lands-list">
            {recentLands.map((land) => (
              <div
                key={land.land_id}
                className="dashboard-land-row"
                onClick={() => navigate(`/lands/${land.public_id}`)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && navigate(`/lands/${land.public_id}`)}
              >
                <div className="dashboard-land-row__icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M3 6l9-4 9 4" />
                    <path d="M3 6v12l9 4 9-4V6" />
                  </svg>
                </div>
                <div className="dashboard-land-row__body">
                  <div className="dashboard-land-row__name">{land.name}</div>
                  <div className="dashboard-land-row__meta">
                    {land.area_hectares || "—"} ha
                    {land.latitude != null ? ` · ${Number(land.latitude).toFixed(2)}°N` : ""}
                  </div>
                </div>
                <span className="dashboard-land-row__chevron">
                  <ChevronRight />
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}