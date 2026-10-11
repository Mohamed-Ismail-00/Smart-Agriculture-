/**
 * components/layout/AppLayout.jsx
 * --------------------------------
 * Root layout shell wrapping all protected pages.
 * Sidebar (left) + Topbar (top) + scrollable content area.
 */

import { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import MobileBottomNav from "./MobileBottomNav";
import { useBreakpoint } from "../../hooks/useBreakpoint";

function isLandDetailRoute(pathname) {
  return /^\/lands\/(?!new$|compare$)[^/]+$/.test(pathname);
}

export default function AppLayout({ children }) {
  const location = useLocation();
  const { isDrawer, isDesktop } = useBreakpoint();
  const isImmersiveDetail = isLandDetailRoute(location.pathname);
  const [isSidebarOpen, setIsSidebarOpen] = useState(() =>
    typeof window !== "undefined" ? window.innerWidth > 1024 : true
  );

  useEffect(() => {
    if (isDrawer) {
      setIsSidebarOpen(false);
    } else {
      setIsSidebarOpen(true);
    }
  }, [isDrawer]);

  const toggleSidebar = () => setIsSidebarOpen(!isSidebarOpen);
  const closeSidebar = () => setIsSidebarOpen(false);

  return (
    <div
      className={`app-shell ${!isSidebarOpen ? "app-shell--collapsed" : ""}${isImmersiveDetail ? " app-shell--land-detail" : ""}`}
    >
      <Sidebar isDrawer={isDrawer} onClose={closeSidebar} />
      {isSidebarOpen && isDrawer && (
        <div 
          className="mobile-sidebar-overlay"
          onClick={closeSidebar}
          aria-hidden="true"
        />
      )}
      <div className="app-shell__main">
        <Topbar onToggleSidebar={toggleSidebar} />
        <main className="app-shell__content">
          <div className="app-shell__content-inner">
            {children}
          </div>
        </main>
        {!isDesktop && <MobileBottomNav />}
      </div>
    </div>
  );
}