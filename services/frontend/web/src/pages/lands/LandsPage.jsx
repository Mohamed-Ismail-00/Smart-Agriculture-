/**
 * pages/lands/LandsPage.jsx — Lands Explorer
 */

import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { deleteLand } from "../../services/api";
import { useLands } from "../../hooks/useLands";
import { useBreakpoint } from "../../hooks/useBreakpoint";
import { useConfirm } from "../../context/ConfirmContext";
import { useNotifications } from "../../context/NotificationContext";
import AuthenticatedImage from "../../components/AuthenticatedImage";
import "../Lands.css";
import "../mobile-home.css";

const FILTERS = [
  { key: "all", label: "All" },
  { key: "healthy", label: "Ready" },
  { key: "warning", label: "Processing" },
  { key: "critical", label: "Error" },
];

function statusColor(status) {
  if (!status) return "info";
  const s = status.toLowerCase();
  if (s === "ready" || s === "active" || s === "completed" || s === "active_partial") return "healthy";
  if (s === "error" || s === "failed" || s.includes("fail") || s.includes("error") || s.includes("not found")) return "critical";
  if (s === "processing" || s.includes("step") || s.includes("fetch") || s.includes("download") || s.includes("generat")) return "warning";
  return "info";
}

function statusLabel(status) {
  const color = statusColor(status);
  if (color === "healthy") return "Ready";
  if (color === "warning") return "Processing";
  if (color === "critical") return "Error";
  return "Info";
}

const HECTARES_PER_FEDDAN = 0.420083;

function formatArea(hectares) {
  if (hectares == null) return "—";
  const ha = Number(hectares);
  return `${ha.toFixed(2)} ha · ${(ha / HECTARES_PER_FEDDAN).toFixed(1)} feddan`;
}

// The place a land was registered at is the first part of its description.
function placeLabel(land) {
  const place = land.description?.split("•")[0].trim();
  return place || `${Number(land.latitude).toFixed(3)}°, ${Number(land.longitude).toFixed(3)}°`;
}

function showStatusDetail(status) {
  if (!status) return false;
  const s = status.toLowerCase();
  if (s === "ready" || s === "active" || s === "active_partial" || s === "completed" || s === "processing") return false;
  return status.length > 14;
}

function ChevronRight() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
    </svg>
  );
}

function LandsMobileCard({ land, onOpen, onDelete }) {
  const color = statusColor(land.status);

  return (
    <div className="lands-mobile-card anim-stagger" onClick={() => onOpen(land.public_id)}>
      <div className={`lands-mobile-card__thumb lands-mobile-card__thumb--${color}`}>
        {land.latest_image_url && (
          <AuthenticatedImage
            src={land.latest_image_url}
            alt=""
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        )}
      </div>
      <div className="lands-mobile-card__body">
        <div className="lands-mobile-card__top">
          <span className="lands-mobile-card__name">{land.name}</span>
          <span className={`lands-mobile-card__badge lands-mobile-card__badge--${color}`}>
            {statusLabel(land.status)}
          </span>
        </div>
        {showStatusDetail(land.status) && (
          <p className="lands-mobile-card__status">{land.status}</p>
        )}
        <div className="lands-mobile-card__meta">
          {formatArea(land.area_hectares)} · {placeLabel(land)}
        </div>
      </div>
      <div className="lands-mobile-card__actions">
        <button
          type="button"
          className="lands-mobile-card__delete"
          title="Delete land"
          aria-label={`Delete ${land.name}`}
          onClick={(e) => onDelete(e, land.public_id, land.name)}
        >
          <TrashIcon />
        </button>
        <span className="lands-mobile-card__chevron" aria-hidden="true">
          <ChevronRight />
        </span>
      </div>
    </div>
  );
}

function PremiumLandCard({ land, index, onOpen, onDelete, colorFn }) {
  const color = colorFn(land.status);
  return (
    <div
      className="premium-land-card anim-stagger"
      style={{ "--stagger-index": index + 1 }}
      onClick={() => onOpen(land.public_id)}
    >
      <div className={`premium-land-card__thumb status-${color}`}>
        {land.latest_image_url && (
          <AuthenticatedImage
            src={land.latest_image_url}
            alt=""
            style={{
              position: "absolute",
              inset: 0,
              width: "100%",
              height: "100%",
              objectFit: "cover",
            }}
          />
        )}
        <div className="thumb-overlay" />
        <span className={`premium-badge badge--${color}`}>
          <span className="badge__dot" />
          {statusLabel(land.status)}
        </span>
      </div>
      <div className="premium-land-card__body">
        <h3 className="premium-land-card__name">{land.name}</h3>
        <div className="premium-land-card__stats">
          <div className="stat-item">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" />
              <circle cx="12" cy="10" r="3" />
            </svg>
            <span>{placeLabel(land)}</span>
          </div>
          <div className="stat-item">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <path d="M3 9h18" />
            </svg>
            <span>{formatArea(land.area_hectares)}</span>
          </div>
        </div>
        <div className="premium-land-card__footer">
          <span className="date-label">Added {new Date(land.created_at).toLocaleDateString()}</span>
          <div style={{ display: "flex", gap: "var(--space-sm)", alignItems: "center" }}>
            <button
              type="button"
              className="icon-btn delete-btn"
              title="Delete land"
              aria-label={`Delete ${land.name}`}
              onClick={(e) => onDelete(e, land.public_id, land.name)}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ width: 16, height: 16 }}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
            <div className="explore-btn">
              Explore
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12" />
                <polyline points="12 5 19 12 12 19" />
              </svg>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LandsPage() {
  const navigate = useNavigate();
  const confirm = useConfirm();
  const { addNotification } = useNotifications();
  const { isDrawer } = useBreakpoint();
  const isMobileLayout = isDrawer;
  const { lands, setLands, loading, error, refetch } = useLands();
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");

  const handleDeleteLand = async (e, publicId, landName) => {
    e.stopPropagation();
    const confirmed = await confirm({
      title: "Delete Land",
      message: `Are you sure you want to delete "${landName}"? This cannot be undone.`,
      confirmLabel: "Delete",
      cancelLabel: "Cancel",
      variant: "danger",
    });
    if (!confirmed) return;
    try {
      await deleteLand(publicId);
      setLands((prev) => prev.filter((l) => l.public_id !== publicId));
    } catch (err) {
      addNotification({
        type: "system",
        severity: "high",
        message: `Failed to delete land: ${err.message}`,
      });
    }
  };

  const searchFiltered = useMemo(
    () => lands.filter((l) => l.name.toLowerCase().includes(search.toLowerCase())),
    [lands, search]
  );

  const filterCounts = useMemo(() => {
    const counts = { all: searchFiltered.length };
    FILTERS.slice(1).forEach((f) => {
      counts[f.key] = searchFiltered.filter((l) => statusColor(l.status) === f.key).length;
    });
    return counts;
  }, [searchFiltered]);

  const filteredLands = useMemo(
    () =>
      searchFiltered.filter((l) => filter === "all" || statusColor(l.status) === filter),
    [searchFiltered, filter]
  );

  const openLand = (publicId) => navigate(`/lands/${publicId}`);

  if (loading) {
    return (
      <div className="anim-fade-in" style={{ padding: "var(--space-3xl)" }}>
        <div className="lands-hero skeleton-hero" />
        <div className={isMobileLayout ? "lands-mobile-list" : "lands-premium-grid"} style={{ marginTop: "var(--space-xl)" }}>
          {[0, 1, 2].map((i) => (
            <div className="card skeleton" key={i} style={{ height: isMobileLayout ? 72 : 280 }} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className={`anim-fade-in lands-page-container${isMobileLayout ? " lands-page--mobile" : ""}`}>
      <div className="lands-hero">
        <div className="lands-hero__content">
          <h1 className="lands-hero__title">My Lands</h1>
          <p className="lands-hero__subtitle">
            {lands.length} registered plot{lands.length !== 1 ? "s" : ""}
          </p>
        </div>
        <div className="lands-hero__blobs">
          <div className="blob blob-1" />
          <div className="blob blob-2" />
        </div>
      </div>

      {/* Mobile sticky toolbar */}
      {isMobileLayout && (
        <div className="lands-toolbar-sticky">
          <div className="lands-toolbar-sticky__search">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              type="search"
              placeholder="Search lands…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search lands"
            />
          </div>
          <div className="lands-filter-scroll">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                type="button"
                className={`lands-filter-pill${filter === f.key ? " lands-filter-pill--active" : ""}`}
                onClick={() => setFilter(f.key)}
              >
                {f.label}
                <span className="lands-filter-pill__count">{filterCounts[f.key]}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Desktop controls */}
      {!isMobileLayout && (
        <div className="lands-glass-controls anim-stagger" style={{ "--stagger-index": 0 }}>
          <div className="lands-glass-controls__left">
            <div className="search-wrapper">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="search-icon">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                type="text"
                className="glass-input"
                placeholder="Search by land name..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <div className="lands-glass-filters">
              {FILTERS.map((f) => (
                <button
                  key={f.key}
                  type="button"
                  className={`glass-filter-btn ${filter === f.key ? "active" : ""}`}
                  onClick={() => setFilter(f.key)}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>
          <button type="button" className="btn btn--primary premium-add-btn" onClick={() => navigate("/lands/new")}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 18, height: 18, flexShrink: 0 }}>
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Add New Land
          </button>
        </div>
      )}

      {error && (
        <div className="alert alert--error" style={{ marginBottom: "var(--space-lg)", borderRadius: "var(--radius-lg)", display: "flex", alignItems: "center", flexWrap: "wrap", gap: "var(--space-sm)" }}>
          <strong>Error:</strong> {error}
          <button type="button" className="btn btn--secondary btn--sm" onClick={refetch} style={{ marginLeft: "auto" }}>
            Retry
          </button>
        </div>
      )}

      {filteredLands.length === 0 && !error && (
        <div className="empty-state premium-empty" style={{ padding: "var(--space-3xl)" }}>
          <div className="empty-icon-wrapper">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" />
              <circle cx="12" cy="10" r="3" />
            </svg>
          </div>
          <h3 className="text-h3">No lands found</h3>
          <p className="text-body-sm" style={{ marginTop: "var(--space-sm)", color: "var(--text-secondary)" }}>
            {search ? `No results for "${search}"` : "Start by registering your first agricultural land."}
          </p>
          {!search && (
            <button type="button" className="btn btn--primary" style={{ marginTop: "var(--space-lg)" }} onClick={() => navigate("/lands/new")}>
              Register Your First Land
            </button>
          )}
        </div>
      )}

      {isMobileLayout ? (
        <div className="lands-mobile-list">
          {filteredLands.map((land, i) => (
            <LandsMobileCard
              key={land.public_id}
              land={land}
              onOpen={openLand}
              onDelete={handleDeleteLand}
            />
          ))}
        </div>
      ) : (
        <div className="lands-premium-grid">
          {filteredLands.map((land, i) => (
            <PremiumLandCard
              key={land.public_id}
              land={land}
              index={i}
              onOpen={openLand}
              onDelete={handleDeleteLand}
              colorFn={statusColor}
            />
          ))}
        </div>
      )}
    </div>
  );
}