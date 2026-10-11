/**
 * hooks/useBreakpoint.js
 * Shared responsive breakpoints for web + React Native migration prep.
 * Single source of truth — replaces scattered window.innerWidth checks.
 */

import { useState, useEffect } from "react";

export const BREAKPOINTS = {
  mobile: 640,
  tablet: 1024,
  drawer: 1024,
};

export function useBreakpoint() {
  const [width, setWidth] = useState(
    typeof window !== "undefined" ? window.innerWidth : BREAKPOINTS.tablet + 1
  );

  useEffect(() => {
    const onResize = () => setWidth(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  return {
    width,
    isMobile: width <= BREAKPOINTS.mobile,
    isTablet: width <= BREAKPOINTS.tablet,
    isDrawer: width <= BREAKPOINTS.drawer,
    isDesktop: width > BREAKPOINTS.tablet,
  };
}