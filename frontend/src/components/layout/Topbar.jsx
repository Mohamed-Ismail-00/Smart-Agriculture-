/**
 * components/layout/Topbar.jsx
 * Top bar with mobile-first search & notification overlays
 */

import { useState, useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { listLands } from "../../services/api";
import { useNotifications } from "../../context/NotificationContext";
import { useBreakpoint } from "../../hooks/useBreakpoint";
import "./Topbar.css";

const PAGE_TITLES = {
  "/dashboard": "Dashboard",
  "/lands": "Lands Explorer",
  "/lands/new": "Add New Land",
  "/lands/compare": "Compare Lands",
  "/profile": "My Profile",
  "/logs": "Activity Logs",
};

const SEVERITY_COLORS = {
  low: "var(--green-500)",
  medium: "var(--amber-500)",
  high: "var(--error)",
  critical: "#7c3aed",
};

const SEVERITY_BG = {
  low: "var(--green-50)",
  medium: "var(--warning-light)",
  high: "var(--error-light)",
  critical: "#f3e8ff",
};

const ALERT_TYPE_LABELS = {
  ai_analysis_complete: "AI Analysis Done",
  ai_analysis_failed: "AI Analysis Failed",
  ndvi_drop: "NDVI Drop",
  heat_stress: "Heat Stress",
  drought: "Drought Alert",
  disease_risk: "Disease Risk",
  ui_message: "System",
  land_created: "Land Added",
};

const ALERT_TYPE_ICONS = {
  ai_analysis_complete: "✨",
  ai_analysis_failed: "⚠️",
  ndvi_drop: "📉",
  heat_stress: "🌡️",
  drought: "🌵",
  disease_risk: "🦠",
  ui_message: "💬",
  land_created: "🌱",
};

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" />
      <path d="M21 21l-4.35-4.35" />
    </svg>
  );
}

function BellIcon({ pulse }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ transition: "transform 0.2s", transform: pulse ? "scale(1.15)" : "scale(1)" }}
    >
      <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 01-3.46 0" />
    </svg>
  );
}

function LandIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 6l9-4 9 4" />
      <path d="M3 6v12l9 4 9-4V6" />
      <path d="M12 22V10" />
    </svg>
  );
}

function ChevronRight() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

function getStatusColor(status) {
  if (!status) return "var(--info)";
  const s = status.toLowerCase();
  if (s.includes("error") || s.includes("fail") || s.includes("not found")) return "var(--error)";
  if (s.includes("processing") || s.includes("step") || s.includes("fetch")) return "var(--warning)";
  return "var(--success)";
}

function formatTime(ts) {
  if (!ts) return "";
  const d = new Date(ts);
  const mins = Math.floor((Date.now() - d.getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  if (mins < 1440) return `${Math.floor(mins / 60)}h ago`;
  return d.toLocaleDateString();
}

function SearchPanel({
  isMobile,
  searchQuery,
  setSearchQuery,
  onClose,
  landsLoading,
  filteredLands,
  onSelectLand,
  getStatusColor: statusColor,
}) {
  const inputRef = useRef(null);

  useEffect(() => {
    const t = setTimeout(() => inputRef.current?.focus(), isMobile ? 80 : 0);
    return () => clearTimeout(t);
  }, [isMobile]);

  const content = (
    <>
      <div className="topbar-search__header">
        <div className="topbar-search__input-wrap">
          <SearchIcon />
          <input
            ref={inputRef}
            className="topbar-search__input"
            placeholder="Search lands by name or ID…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Search lands"
          />
          {searchQuery && (
            <button
              type="button"
              className="topbar-search__clear"
              onClick={() => setSearchQuery("")}
              aria-label="Clear search"
            >
              ×
            </button>
          )}
        </div>
        {isMobile && (
          <button type="button" className="topbar-search__cancel" onClick={onClose}>
            Cancel
          </button>
        )}
        {!isMobile && (
          <button
            type="button"
            className="topbar-search__clear"
            onClick={onClose}
            aria-label="Close search"
            style={{ width: 36, height: 36, fontSize: 20 }}
          >
            ×
          </button>
        )}
      </div>

      <div className="topbar-search__results">
        {landsLoading && (
          <div className="topbar-search__loading">Loading your lands…</div>
        )}

        {!landsLoading && filteredLands.length === 0 && (
          <div className="topbar-search__empty">
            <div className="topbar-search__empty-icon">🔍</div>
            {searchQuery
              ? `No lands match "${searchQuery}"`
              : "No lands yet. Add your first land to get started."}
          </div>
        )}

        {!landsLoading && filteredLands.length > 0 && (
          <>
            <div className="topbar-search__section-label">
              {searchQuery ? "Results" : "Your lands"}
            </div>
            {filteredLands.map((land) => (
              <button
                key={land.land_id}
                type="button"
                className="topbar-search__result"
                onClick={() => onSelectLand(land.public_id || land.land_id)}
              >
                <div className="topbar-search__result-icon">
                  <LandIcon />
                </div>
                <div className="topbar-search__result-body">
                  <span className="topbar-search__result-name">
                    {land.name || `Land #${land.land_id}`}
                  </span>
                  <span className="topbar-search__result-meta">
                    <span
                      className="topbar-search__result-status"
                      style={{ backgroundColor: statusColor(land.status) }}
                    />
                    <span>
                      {(land.status || "active").split(":")[0]}
                      {land.area_hectares ? ` · ${land.area_hectares} ha` : ""}
                    </span>
                  </span>
                </div>
                <span className="topbar-search__result-chevron">
                  <ChevronRight />
                </span>
              </button>
            ))}
          </>
        )}
      </div>
    </>
  );

  if (isMobile) {
    return <div className="topbar-search-sheet">{content}</div>;
  }

  return <div className="topbar__search-panel--desktop">{content}</div>;
}

function NotifPanel({
  isMobile,
  notifLoading,
  notifications,
  unreadCount,
  onItemClick,
  onClear,
  onRefresh,
  getSeverityColor,
  getAlertLabel,
  getAlertIcon,
  formatTime: fmtTime,
}) {
  const hasLandLink = (n) => n.payload?.public_id || n.land_id;

  const content = (
    <>
      {!isMobile && (
        <div className="topbar-notif__header">
          <span className="topbar-notif__title">Notifications</span>
          <div className="topbar-notif__meta">
            {unreadCount > 0 && (
              <span className="topbar-notif__count-badge">{unreadCount} new</span>
            )}
            <span className="topbar-notif__total">{notifications.length} total</span>
          </div>
        </div>
      )}

      {isMobile && (
        <>
          <div className="topbar-sheet-grab">
            <div className="topbar-sheet-grab__bar" />
          </div>
          <div className="topbar-notif__header">
            <span className="topbar-notif__title">Notifications</span>
            <div className="topbar-notif__meta">
              {unreadCount > 0 && (
                <span className="topbar-notif__count-badge">{unreadCount} new</span>
              )}
              <span className="topbar-notif__total">{notifications.length}</span>
            </div>
          </div>
        </>
      )}

      <div className="topbar-notif__list">
        {notifLoading && (
          <div className="topbar-notif__loading">Loading alerts…</div>
        )}

        {!notifLoading && notifications.length === 0 && (
          <div className="topbar-notif__empty">
            <div className="topbar-notif__empty-icon">🔔</div>
            <strong style={{ display: "block", marginBottom: 6, color: "var(--text-primary)" }}>
              All caught up
            </strong>
            AI analyses and monitoring alerts will appear here.
          </div>
        )}

        {!notifLoading &&
          notifications.map((n) => {
            const severity = n.severity || "low";
            const type = n.alert_type || n.type;
            return (
              <button
                key={n.id}
                type="button"
                className={`topbar-notif__item${!n.is_read ? " topbar-notif__item--unread" : ""}`}
                onClick={() => onItemClick(n)}
              >
                <div
                  className="topbar-notif__item-icon"
                  style={{ background: SEVERITY_BG[severity] || SEVERITY_BG.low }}
                >
                  {getAlertIcon(type)}
                </div>
                <div className="topbar-notif__item-body">
                  <span
                    className="topbar-notif__item-label"
                    style={{ color: getSeverityColor(severity) }}
                  >
                    {getAlertLabel(type)}
                  </span>
                  <span className="topbar-notif__item-msg">{n.message || n.msg || "Alert"}</span>
                  <span className="topbar-notif__item-time">{fmtTime(n.timestamp)}</span>
                </div>
                {hasLandLink(n) && (
                  <span className="topbar-notif__item-arrow">
                    <ChevronRight />
                  </span>
                )}
              </button>
            );
          })}
      </div>

      <div className="topbar-notif__footer">
        <button type="button" className="topbar-notif__btn" onClick={onClear}>
          Clear all
        </button>
        <button type="button" className="topbar-notif__btn topbar-notif__btn--primary" onClick={onRefresh}>
          Refresh
        </button>
      </div>
    </>
  );

  if (isMobile) {
    return <div className="topbar-notif-sheet topbar-notif-sheet--above-nav">{content}</div>;
  }

  return <div className="topbar__notif-dropdown--desktop">{content}</div>;
}

export default function Topbar({ onToggleSidebar }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { isDrawer } = useBreakpoint();
  const isMobile = isDrawer;

  const {
    notifications,
    unreadCount,
    markAllRead,
    markRead,
    loadServerNotifications,
    clearAll,
    addNotification,
  } = useNotifications();

  const [searchOpen, setSearchOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [lands, setLands] = useState([]);
  const [landsLoading, setLandsLoading] = useState(false);
  const [notifLoading, setNotifLoading] = useState(false);
  const [badgePulse, setBadgePulse] = useState(false);

  const searchRef = useRef(null);
  const notifRef = useRef(null);
  const prevUnreadRef = useRef(unreadCount);

  const overlayOpen = isMobile && (searchOpen || notifOpen);

  const getTitle = () => {
    if (PAGE_TITLES[location.pathname]) return PAGE_TITLES[location.pathname];
    if (location.pathname.startsWith("/lands/")) return "Land Details";
    return "Dashboard";
  };

  useEffect(() => {
    if (unreadCount > prevUnreadRef.current) {
      setBadgePulse(true);
      const t = setTimeout(() => setBadgePulse(false), 600);
      return () => clearTimeout(t);
    }
    prevUnreadRef.current = unreadCount;
  }, [unreadCount]);

  useEffect(() => {
    setSearchOpen(false);
    setNotifOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") {
        setSearchOpen(false);
        setNotifOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!overlayOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [overlayOpen]);

  useEffect(() => {
    const closeOverlaysForMap = () => {
      if (document.body.classList.contains("map-draw-body-lock")) {
        setSearchOpen(false);
        setNotifOpen(false);
        setSearchQuery("");
      }
    };
    const observer = new MutationObserver(closeOverlaysForMap);
    observer.observe(document.body, { attributes: true, attributeFilter: ["class"] });
    closeOverlaysForMap();
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (isMobile) return;
    const handler = (e) => {
      if (searchOpen && searchRef.current && !searchRef.current.contains(e.target)) {
        setSearchOpen(false);
      }
      if (notifOpen && notifRef.current && !notifRef.current.contains(e.target)) {
        setNotifOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [searchOpen, notifOpen, isMobile]);

  const openSearch = async () => {
    setNotifOpen(false);
    const next = !searchOpen;
    setSearchOpen(next);
    if (next && lands.length === 0) {
      setLandsLoading(true);
      try {
        const res = await listLands();
        const items = res?.lands || res?.data?.lands || [];
        setLands(items);
      } catch {
        setLands([]);
      } finally {
        setLandsLoading(false);
      }
    }
  };

  const openNotifs = async () => {
    setSearchOpen(false);
    const next = !notifOpen;
    setNotifOpen(next);
    if (next) {
      setNotifLoading(true);
      try {
        await loadServerNotifications();
        if (unreadCount > 0) await markAllRead();
      } finally {
        setNotifLoading(false);
      }
    }
  };

  const closeSearch = () => {
    setSearchOpen(false);
    setSearchQuery("");
  };

  const filteredLands = searchQuery.trim()
    ? lands.filter(
        (l) =>
          (l.name || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
          String(l.land_id || "").includes(searchQuery)
      )
    : lands
        .filter((l) => {
          const s = (l.status || "").toLowerCase();
          return !s.includes("error") && !s.includes("fail") && !s.includes("not found");
        })
        .slice(0, 8);

  const goToLand = (landId) => {
    closeSearch();
    navigate(`/lands/${landId}`);
  };

  const handleNotifClick = async (n) => {
    setNotifOpen(false);
    if (!n.is_read) await markRead(n.id);
    if (n.payload?.public_id) navigate(`/lands/${n.payload.public_id}`);
    else if (n.land_id) navigate(`/lands/${n.land_id}`);
  };

  const handleClear = () => {
    clearAll();
    setTimeout(
      () =>
        addNotification({
          type: "system",
          severity: "low",
          message: "Notifications cleared. New alerts will appear here.",
        }),
      120
    );
  };

  const getSeverityColor = (severity) => SEVERITY_COLORS[severity] || "var(--text-secondary)";
  const getAlertLabel = (type) => ALERT_TYPE_LABELS[type] || (type || "alert").replace(/_/g, " ");
  const getAlertIcon = (type) => ALERT_TYPE_ICONS[type] || "📌";

  return (
    <header className="topbar" id="app-topbar">
      <div className="topbar__left">
        <button
          className="topbar__icon-btn"
          onClick={onToggleSidebar}
          aria-label="Toggle menu"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 22, height: 22 }}>
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
        <h1 className="topbar__page-title">{getTitle()}</h1>
      </div>

      <div className="topbar__right">
        {/* Notifications */}
        <div ref={notifRef} style={{ position: "relative" }}>
          <button
            type="button"
            className={`topbar__icon-btn${notifOpen ? " topbar__icon-btn--active" : ""}`}
            aria-label="Notifications"
            aria-expanded={notifOpen}
            id="topbar-notifications"
            onClick={openNotifs}
          >
            <BellIcon pulse={badgePulse} />
            {unreadCount > 0 && (
              <span className={`topbar__badge${badgePulse ? " topbar__badge--pulse" : ""}`}>
                {unreadCount > 99 ? "99+" : unreadCount}
              </span>
            )}
          </button>

          {notifOpen && !isMobile && (
            <NotifPanel
              isMobile={false}
              notifLoading={notifLoading}
              notifications={notifications}
              unreadCount={unreadCount}
              onItemClick={handleNotifClick}
              onClear={handleClear}
              onRefresh={() => loadServerNotifications()}
              getSeverityColor={getSeverityColor}
              getAlertLabel={getAlertLabel}
              getAlertIcon={getAlertIcon}
              formatTime={formatTime}
            />
          )}
        </div>

        {/* Search */}
        <div ref={searchRef} style={{ position: "relative" }}>
          <button
            type="button"
            className={`topbar__icon-btn${searchOpen ? " topbar__icon-btn--active" : ""}`}
            aria-label="Search lands"
            aria-expanded={searchOpen}
            id="topbar-search"
            onClick={openSearch}
          >
            <SearchIcon />
          </button>

          {searchOpen && !isMobile && (
            <SearchPanel
              isMobile={false}
              searchQuery={searchQuery}
              setSearchQuery={setSearchQuery}
              onClose={closeSearch}
              landsLoading={landsLoading}
              filteredLands={filteredLands}
              onSelectLand={goToLand}
              getStatusColor={getStatusColor}
            />
          )}
        </div>
      </div>

      {/* Mobile full-screen overlays */}
      {isMobile && overlayOpen && (
        <div
          className="topbar-overlay-backdrop topbar-overlay-backdrop--above-nav"
          onClick={() => {
            setSearchOpen(false);
            setNotifOpen(false);
            setSearchQuery("");
          }}
          aria-hidden="true"
        />
      )}

      {isMobile && searchOpen && (
        <SearchPanel
          isMobile
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          onClose={closeSearch}
          landsLoading={landsLoading}
          filteredLands={filteredLands}
          onSelectLand={goToLand}
          getStatusColor={getStatusColor}
        />
      )}

      {isMobile && notifOpen && (
        <NotifPanel
          isMobile
          notifLoading={notifLoading}
          notifications={notifications}
          unreadCount={unreadCount}
          onItemClick={handleNotifClick}
          onClear={handleClear}
          onRefresh={() => loadServerNotifications()}
          getSeverityColor={getSeverityColor}
          getAlertLabel={getAlertLabel}
          getAlertIcon={getAlertIcon}
          formatTime={formatTime}
        />
      )}
    </header>
  );
}