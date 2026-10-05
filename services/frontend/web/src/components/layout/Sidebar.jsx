/**
 * components/layout/Sidebar.jsx
 * ----------------------------
 * Main sidebar navigation with dark green theme.
 * Uses NavLink for automatic active state highlighting.
 */

import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

/* --- SVG Icon Components (inline, no external deps) --- */

const icons = {
  dashboard: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="4" rx="1" />
      <rect x="3" y="14" width="7" height="4" rx="1" />
      <rect x="14" y="11" width="7" height="7" rx="1" />
    </svg>
  ),
  lands: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 6l9-4 9 4" />
      <path d="M3 6v12l9 4 9-4V6" />
      <path d="M12 22V10" />
    </svg>
  ),
  addLand: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v8M8 12h8" />
    </svg>
  ),
  compare: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 3H5a2 2 0 00-2 2v14a2 2 0 002 2h5" />
      <path d="M14 3h5a2 2 0 012 2v14a2 2 0 01-2 2h-5" />
      <path d="M12 3v18" />
      <path d="M7 8h3M7 12h3M14 8h3M14 12h3" />
    </svg>
  ),
  methodology: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2L2 7l10 5 10-5-10-5z" />
      <path d="M2 17l10 5 10-5" />
      <path d="M2 12l10 5 10-5" />
    </svg>
  ),
  team: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 00-3-3.87" />
      <path d="M16 3.13a4 4 0 010 7.75" />
    </svg>
  ),
  about: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4M12 8h.01" />
    </svg>
  ),
  profile: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  ),
  logs: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M16 13H8M16 17H8M10 9H8" />
    </svg>
  ),
  logout: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  ),
};

const baseNavItems = [
  { section: "MAIN" },
  { to: "/dashboard", icon: "dashboard", label: "Dashboard" },
  { to: "/lands",     icon: "lands",     label: "Lands Explorer" },
  { to: "/lands/new", icon: "addLand",   label: "Add New Land" },

  { section: "INSIGHTS" },
  { to: "/lands/compare", icon: "compare", label: "Compare Lands" },
  { to: "/methodology", icon: "methodology", label: "Methodology" },

  { section: "GENERAL" },
  { to: "/about",   icon: "about",   label: "About" },
  { to: "/profile", icon: "profile", label: "Profile" },
];

export default function Sidebar({ isDrawer, onClose }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const navItems = [
    ...baseNavItems,
    ...(user?.role === "admin" ? [{ to: "/logs", icon: "logs", label: "Activity Logs" }] : []),
  ];

  const handleNavClick = () => {
    if (isDrawer && onClose) onClose();
  };

  const handleLogout = async () => {
    await logout();
    navigate("/login");
    if (isDrawer && onClose) onClose();
  };

  /** Get user's initials for avatar */
  const getInitials = () => {
    if (!user?.email) return "?";
    return user.email.charAt(0).toUpperCase();
  };

  return (
    <aside className="sidebar" id="app-sidebar">
      {/* Logo */}
      <div className="sidebar__header">
        <div className="sidebar__logo-icon">
          <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M16 2C16 2 6 10 6 18C6 23.5 10.5 28 16 28C21.5 28 26 23.5 26 18C26 10 16 2 16 2Z" fill="rgba(255,255,255,0.9)"/>
            <path d="M16 8C16 8 10 14 10 19C10 22.3 12.7 25 16 25C19.3 25 22 22.3 22 19C22 14 16 8 16 8Z" fill="rgba(255,255,255,0.5)"/>
          </svg>
        </div>
        <span className="sidebar__logo-text">AgriData Egypt</span>

        {isDrawer && onClose && (
          <button
            onClick={onClose}
            className="sidebar__close-btn touch-target"
            aria-label="Close sidebar"
          >
            ×
          </button>
        )}
      </div>

      {/* Navigation */}
      <nav className="sidebar__nav">
        {navItems.map((item, i) => {
          if (item.section) {
            return (
              <div className="sidebar__section-label" key={`section-${i}`}>
                {item.section}
              </div>
            );
          }

          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/dashboard" || item.to === "/lands"}
              className={({ isActive }) =>
                `sidebar__link${isActive ? " sidebar__link--active" : ""}`
              }
              onClick={handleNavClick}
            >
              <span className="sidebar__link-icon">{icons[item.icon]}</span>
              <span className="sidebar__link-text">{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Footer / User */}
      <div className="sidebar__footer">
        <div className="sidebar__user">
          <div className="sidebar__user-avatar">{getInitials()}</div>
          <div className="sidebar__user-info">
            <div className="sidebar__user-name">{user?.email || "User"}</div>
            <div className="sidebar__user-role">{user?.role || "viewer"}</div>
          </div>
          <button
            className="sidebar__logout-btn"
            onClick={handleLogout}
            aria-label="Sign out"
            title="Sign out"
            id="sidebar-logout-btn"
          >
            {icons.logout}
          </button>
        </div>
      </div>
    </aside>
  );
}
