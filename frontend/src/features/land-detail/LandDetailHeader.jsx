/**
 * LandDetailHeader — title, meta, actions, settings & progress modals
 */

import { useState, useRef, useEffect } from "react";
import { getLandStatusBadge, formatTaskStatus, formatPipelineWarnings } from "./landDetailUtils";

export default function LandDetailHeader({
  land,
  reanalyzing,
  isExporting,
  showSettings,
  setShowSettings,
  showProgressModal,
  setShowProgressModal,
  intervalDays,
  setIntervalDays,
  onBack,
  onDelete,
  onExport,
  onReanalyze,
  onSaveSettings,
  isMobile = false,
}) {
  const statusBadge = getLandStatusBadge(land.status);
  const pipelineWarnings = land?.metadata_?.pipeline_warnings;
  const pipelineWarningText = formatPipelineWarnings(pipelineWarnings);
  const [menuOpen, setMenuOpen] = useState(false);
  const [showReanalyzeModal, setShowReanalyzeModal] = useState(false);
  const [refreshOptions, setRefreshOptions] = useState({
    environment: true,
    satellite: true,
    crops: true,
  });
  const menuRef = useRef(null);

  const refreshLabels = {
    environment: "Environment (climate, soil moisture, water)",
    satellite: "Satellite imagery (Sentinel-2)",
    crops: "Crop NDVI & zones",
  };

  const toggleRefresh = (key) => {
    setRefreshOptions((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleConfirmReanalyze = () => {
    const selected = Object.entries(refreshOptions)
      .filter(([, enabled]) => enabled)
      .map(([key]) => key);
    if (selected.length === 0) return;
    setShowReanalyzeModal(false);
    onReanalyze(selected);
  };

  useEffect(() => {
    if (!menuOpen) return;
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("touchstart", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("touchstart", handleClickOutside);
    };
  }, [menuOpen]);

  const closeMenu = () => setMenuOpen(false);

  const handleAction = (action) => {
    closeMenu();
    action();
  };

  return (
    <>
      <div className={`land-detail__header${isMobile ? " land-detail__header--mobile" : ""}`}>
        {isMobile ? (
          <div className="land-detail__header-top">
            <button className="land-detail__back-btn" onClick={onBack} aria-label="Back to lands">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M19 12H5M12 19l-7-7 7-7" />
              </svg>
            </button>
            <div className="land-detail__header-title-wrap">
              <h1 className="land-detail__title land-detail__title--mobile">{land.name}</h1>
              <span className={`badge badge--${statusBadge} badge--sm`}>
                <span className="badge__dot" />
                {land.status.charAt(0).toUpperCase() + land.status.slice(1)}
              </span>
            </div>
            <div className="land-detail__actions-menu" ref={menuRef}>
              <button
                className="land-detail__menu-btn"
                onClick={() => setMenuOpen((o) => !o)}
                aria-label="Land actions"
                aria-expanded={menuOpen}
              >
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <circle cx="12" cy="5" r="2" />
                  <circle cx="12" cy="12" r="2" />
                  <circle cx="12" cy="19" r="2" />
                </svg>
              </button>
              {menuOpen && (
                <div className="land-detail__actions-dropdown">
                  <button
                    className="land-detail__actions-dropdown-item land-detail__actions-dropdown-item--primary"
                    onClick={() => handleAction(() => setShowReanalyzeModal(true))}
                    disabled={reanalyzing}
                  >
                    {reanalyzing ? "Analyzing…" : "Re-Analyze"}
                  </button>
                  <button
                    className="land-detail__actions-dropdown-item"
                    onClick={() => handleAction(onExport)}
                    disabled={isExporting}
                  >
                    {isExporting ? "Exporting..." : "Export Data"}
                  </button>
                  <button
                    className="land-detail__actions-dropdown-item"
                    onClick={() => handleAction(() => setShowSettings(true))}
                  >
                    Settings
                  </button>
                  <button
                    className="land-detail__actions-dropdown-item land-detail__actions-dropdown-item--danger"
                    onClick={() => handleAction(onDelete)}
                  >
                    Delete Land
                  </button>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="land-detail__header-info">
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)", marginBottom: "var(--space-sm)" }}>
              <button className="btn btn--ghost btn--sm" onClick={onBack}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 16, height: 16 }}>
                  <path d="M19 12H5M12 19l-7-7 7-7" />
                </svg>
                Back
              </button>
            </div>
            <h1 className="land-detail__title">{land.name}</h1>
          </div>
        )}

        <div className={`land-detail__meta${isMobile ? " land-detail__meta--mobile" : ""}`}>
          <span className="land-detail__meta-item">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" />
              <circle cx="12" cy="10" r="3" />
            </svg>
            {land.latitude.toFixed(4)}°N, {land.longitude.toFixed(4)}°E
          </span>
          <span className="land-detail__meta-item">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <path d="M3 9h18M9 3v18" />
            </svg>
            {land.area_hectares} ha
          </span>
          {!isMobile && (
            <span className={`badge badge--${statusBadge}`}>
              <span className="badge__dot" />
              {land.status.charAt(0).toUpperCase() + land.status.slice(1)}
            </span>
          )}
        </div>

        {land.description && (
          <p className={`land-detail__description${isMobile ? " land-detail__description--mobile" : ""}`}>
            {land.description}
          </p>
        )}

        {!isMobile && (
          <div className="land-detail__header-actions">
            <button
              className="btn btn--ghost btn--sm"
              onClick={onDelete}
              style={{
                color: "var(--error)",
                border: "1px solid rgba(239,68,68,0.25)",
                background: "rgba(239,68,68,0.08)",
                minHeight: "44px",
              }}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ width: 16, height: 16, marginRight: 6 }}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              Delete
            </button>
            <button className="btn btn--secondary btn--sm" onClick={() => setShowSettings(true)} style={{ minHeight: "44px" }}>
              Settings
            </button>
            <button className="btn btn--secondary btn--sm" onClick={onExport} disabled={isExporting} style={{ minHeight: "44px" }}>
              {isExporting ? "Exporting..." : "Export"}
            </button>
            <button
              className="btn btn--primary btn--sm"
              onClick={() => setShowReanalyzeModal(true)}
              disabled={reanalyzing}
              style={{ paddingLeft: "var(--space-lg)", paddingRight: "var(--space-lg)", minHeight: "44px" }}
            >
              {reanalyzing ? "Analyzing…" : "Re-Analyze"}
            </button>
          </div>
        )}
      </div>

      {showReanalyzeModal && (
        <div
          className="modal-overlay"
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 100, display: "flex", alignItems: "flex-end", justifyContent: "center", padding: "var(--space-md)" }}
          onClick={() => setShowReanalyzeModal(false)}
        >
          <div className="card modal-sheet" style={{ width: "100%", maxWidth: 420, padding: "var(--space-lg)" }} onClick={(e) => e.stopPropagation()}>
            <h2 className="text-h3" style={{ marginBottom: "var(--space-sm)" }}>Re-Analyze Land</h2>
            <p className="text-body-sm" style={{ marginBottom: "var(--space-md)", color: "var(--text-secondary)" }}>
              Choose which data to refresh. Existing history outside the environment window is kept.
            </p>
            <div className="land-detail-reanalyze-options">
              {Object.entries(refreshLabels).map(([key, label]) => (
                <label key={key} className="land-detail-reanalyze-option">
                  <input
                    type="checkbox"
                    checked={refreshOptions[key]}
                    onChange={() => toggleRefresh(key)}
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-sm)", marginTop: "var(--space-lg)" }}>
              <button className="btn btn--ghost" onClick={() => setShowReanalyzeModal(false)}>Cancel</button>
              <button
                className="btn btn--primary"
                onClick={handleConfirmReanalyze}
                disabled={!Object.values(refreshOptions).some(Boolean)}
              >
                Start Refresh
              </button>
            </div>
          </div>
        </div>
      )}

      {showSettings && (
        <div
          className="modal-overlay"
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 100, display: "flex", alignItems: "flex-end", justifyContent: "center", padding: "var(--space-md)" }}
          onClick={() => setShowSettings(false)}
        >
          <div className="card modal-sheet" style={{ width: "100%", maxWidth: 420, padding: "var(--space-lg)" }} onClick={(e) => e.stopPropagation()}>
            <h2 className="text-h3" style={{ marginBottom: "var(--space-md)" }}>Land Settings</h2>
            <div className="form-group">
              <label className="form-label">Data Update Period</label>
              <select className="form-control" value={intervalDays} onChange={(e) => setIntervalDays(e.target.value)}>
                <option value="7">Every 7 days (weekly)</option>
                <option value="14">Every 14 days</option>
                <option value="16">Every 16 days (Sentinel-2 default)</option>
                <option value="30">Every 30 days (monthly)</option>
              </select>
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-sm)", marginTop: "var(--space-lg)" }}>
              <button className="btn btn--ghost" onClick={() => setShowSettings(false)}>Cancel</button>
              <button className="btn btn--primary" onClick={onSaveSettings}>Save</button>
            </div>
          </div>
        </div>
      )}

      {pipelineWarningText && !reanalyzing && (
        <div
          className="card anim-fade-in"
          style={{
            marginBottom: "var(--space-md)",
            padding: "12px 16px",
            borderLeft: "3px solid var(--warning)",
          }}
        >
          <p className="text-body-sm" style={{ margin: 0 }}>
            Some data could not be fetched during setup ({pipelineWarningText}).
            Use <strong>Re-analyze</strong> to retry satellite imagery and other missing sections.
          </p>
        </div>
      )}

      {reanalyzing && !showProgressModal && (
        <button
          type="button"
          className="land-detail-task-banner anim-fade-in"
          onClick={() => setShowProgressModal(true)}
        >
          <span className="land-detail-task-banner__icon" aria-hidden="true">
            <span className="spinner" />
          </span>
          <span className="land-detail-task-banner__copy">
            <span className="land-detail-task-banner__title">Analysis in progress</span>
            <span className="land-detail-task-banner__status">{formatTaskStatus(land.status)}</span>
          </span>
          <span className="land-detail-task-banner__action">View</span>
        </button>
      )}

      {showProgressModal && (
        <div
          className="land-detail-task-overlay anim-fade-in"
          onClick={() => setShowProgressModal(false)}
          role="presentation"
        >
          <div
            className="land-detail-task-sheet anim-slide-up"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-labelledby="land-task-title"
            aria-describedby="land-task-desc"
          >
            <div className="land-detail-task-sheet__grab" aria-hidden="true">
              <span />
            </div>
            <div className="land-detail-task-sheet__top">
              <div className="land-detail-task-sheet__heading">
                <span className="land-detail-task-sheet__icon" aria-hidden="true">
                  <span className="spinner" />
                </span>
                <div>
                  <h2 id="land-task-title" className="land-detail-task-sheet__title">Updating your land</h2>
                  <p id="land-task-desc" className="land-detail-task-sheet__subtitle">
                    Keep browsing — data will refresh automatically when ready.
                  </p>
                </div>
              </div>
              <button
                type="button"
                className="land-detail-task-sheet__minimize"
                onClick={() => setShowProgressModal(false)}
              >
                Minimize
              </button>
            </div>
            <div className="land-detail-task-sheet__progress" aria-hidden="true">
              <div className="land-detail-task-sheet__progress-fill" />
            </div>
            <div className="land-detail-task-sheet__status-card">
              <span className="land-detail-task-sheet__status-label">Current step</span>
              <span className="land-detail-task-sheet__status-value">{formatTaskStatus(land.status)}</span>
            </div>
            <ul className="land-detail-task-sheet__steps">
              <li className="land-detail-task-sheet__step land-detail-task-sheet__step--done">
                <span className="land-detail-task-sheet__step-dot">✓</span>
                Land registered
              </li>
              <li className="land-detail-task-sheet__step land-detail-task-sheet__step--active">
                <span className="land-detail-task-sheet__step-dot">
                  <span className="spinner" />
                </span>
                Satellite &amp; environmental data
              </li>
              <li className="land-detail-task-sheet__step">
                <span className="land-detail-task-sheet__step-dot">3</span>
                Dashboard ready
              </li>
            </ul>
          </div>
        </div>
      )}
    </>
  );
}