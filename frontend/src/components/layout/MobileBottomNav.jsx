/**
 * MobileBottomNav — bottom tab bar (RN tab navigator preview)
 */

import { NavLink, useLocation } from "react-router-dom";

const TABS = [
  {
    to: "/dashboard",
    label: "Home",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 9.5L12 3l9 6.5V20a1 1 0 01-1 1h-5v-6H9v6H4a1 1 0 01-1-1V9.5z" />
      </svg>
    ),
  },
  {
    to: "/lands",
    label: "Lands",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 6l9-4 9 4" />
        <path d="M3 6v12l9 4 9-4V6" />
        <path d="M12 22V10" />
      </svg>
    ),
  },
  {
    to: "/lands/new",
    label: "Add",
    isFab: true,
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <line x1="12" y1="5" x2="12" y2="19" />
        <line x1="5" y1="12" x2="19" y2="12" />
      </svg>
    ),
  },
  {
    to: "/lands/compare",
    label: "Compare",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M10 3H5a2 2 0 00-2 2v14a2 2 0 002 2h5" />
        <path d="M14 3h5a2 2 0 012 2v14a2 2 0 01-2 2h-5" />
        <path d="M12 3v18" />
      </svg>
    ),
  },
  {
    to: "/profile",
    label: "Profile",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
        <circle cx="12" cy="7" r="4" />
      </svg>
    ),
  },
];

export default function MobileBottomNav() {
  const location = useLocation();

  const isActive = (to) => {
    if (to === "/lands") {
      return location.pathname === "/lands" || /^\/lands\/(?!new$|compare$)[^/]+$/.test(location.pathname);
    }
    if (to === "/dashboard") return location.pathname === "/dashboard";
    return location.pathname.startsWith(to);
  };

  return (
    <nav className="mobile-bottom-nav" aria-label="Main navigation">
      {TABS.map((tab) =>
        tab.isFab ? (
          <NavLink
            key={tab.to}
            to={tab.to}
            className="mobile-bottom-nav__fab"
            aria-label={tab.label}
          >
            {tab.icon}
          </NavLink>
        ) : (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={`mobile-bottom-nav__item${isActive(tab.to) ? " mobile-bottom-nav__item--active" : ""}`}
          >
            <span className="mobile-bottom-nav__icon">{tab.icon}</span>
            <span className="mobile-bottom-nav__label">{tab.label}</span>
          </NavLink>
        )
      )}
    </nav>
  );
}