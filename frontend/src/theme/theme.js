/**
 * theme/theme.js
 * Design tokens shared between web CSS and future React Native StyleSheet.
 * Keep in sync with :root variables in index.css.
 */

export const colors = {
  green50: "#f0fdf4",
  green100: "#dcfce7",
  green500: "#22c55e",
  green600: "#16a34a",
  green700: "#15803d",
  green800: "#166534",
  green950: "#052e16",
  gray50: "#f9fafb",
  gray100: "#f3f4f6",
  gray200: "#e5e7eb",
  gray300: "#d1d5db",
  gray400: "#9ca3af",
  gray500: "#6b7280",
  gray800: "#1f2937",
  gray900: "#111827",
  amber500: "#f59e0b",
  error: "#ef4444",
  warning: "#f59e0b",
  success: "#22c55e",
  info: "#3b82f6",
  bgPrimary: "rgba(255, 255, 255, 0.7)",
  bgSecondary: "#f4f7f6",
  textPrimary: "#111827",
  textSecondary: "#6b7280",
  border: "#e5e7eb",
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  "2xl": 48,
  "3xl": 64,
};

export const radius = {
  sm: 6,
  md: 10,
  lg: 16,
  xl: 24,
  full: 9999,
};

export const layout = {
  sidebarWidth: 260,
  topbarHeight: 56,
  contentMaxWidth: 1400,
  touchTarget: 44,
};

export const breakpoints = {
  mobile: 640,
  tablet: 1024,
};