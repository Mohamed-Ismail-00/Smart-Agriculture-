/**
 * services/api.js
 * ---------------
 * Central API client for communicating with the backend.
 *
 * All backend calls go through here so that:
 * - Base URL is configured in one place
 * - Auth token is attached automatically
 * - Error handling is consistent
 *
 * Backend endpoints (FastAPI at /api/v1):
 *   Auth:   POST /auth/register, POST /auth/login, GET /auth/me, POST /auth/logout
 *   Lands:  POST /lands/discover, GET /lands/{id}, GET /lands/{id}/timeseries, GET /lands/{id}/images
 *   Health: GET /api/health
 */

// For web (behind nginx or Vite proxy): "/api/v1"
// For mobile / direct: use full URL e.g. "http://10.0.2.2:8000/api/v1" (Android emulator) or your LAN IP
const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";

// Token storage - can be overridden for React Native (AsyncStorage / SecureStore)
let _getToken = () => localStorage.getItem("agri_token");
let _setToken = (t) => localStorage.setItem("agri_token", t);
let _getRefresh = () => localStorage.getItem("agri_refresh_token");
let _setRefresh = (t) => localStorage.setItem("agri_refresh_token", t);
let _clear = () => {
  localStorage.removeItem("agri_token");
  localStorage.removeItem("agri_refresh_token");
};

export function configureTokenStorage({ getToken, setToken, getRefreshToken, setRefreshToken, clearTokens }) {
  if (getToken) _getToken = getToken;
  if (setToken) _setToken = setToken;
  if (getRefreshToken) _getRefresh = getRefreshToken;
  if (setRefreshToken) _setRefresh = setRefreshToken;
  if (clearTokens) _clear = clearTokens;
}

let accessToken = _getToken();
let refreshToken = _getRefresh();

export function getToken() {
  return _getToken();
}

export function getRefreshToken() {
  return _getRefresh();
}

export function setTokens(access, refresh) {
  accessToken = access;
  refreshToken = refresh;
  if (access != null) _setToken(access);
  if (refresh != null) _setRefresh(refresh);
}

export function clearToken() {
  accessToken = null;
  refreshToken = null;
  _clear();
}

/**
 * Make an authenticated API request.
 * Supports automatic token refresh on 401.
 */
let isRefreshing = false;
let refreshSubscribers = [];

function stringifyApiErrorPart(part) {
  if (typeof part === "string") return part;
  if (part == null) return "";
  if (typeof part === "object") {
    if (typeof part.msg === "string") return part.msg;
    if (typeof part.message === "string") return part.message;
    if (typeof part.detail === "string") return part.detail;
    try {
      return JSON.stringify(part);
    } catch {
      return "Request failed.";
    }
  }
  return String(part);
}

function extractApiErrorMessage(data, fallback) {
  if (!data) return fallback;
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail
      .map((entry) => stringifyApiErrorPart(entry?.msg ?? entry))
      .filter(Boolean)
      .join(", ") || fallback;
  }
  if (typeof data.message === "string") return data.message;
  if (data.detail && typeof data.detail === "object") {
    return stringifyApiErrorPart(data.detail);
  }
  return fallback;
}

function subscribeTokenRefresh(cb) {
  refreshSubscribers.push(cb);
}

function onRefreshed(newAccess) {
  refreshSubscribers.forEach((cb) => cb(newAccess));
  refreshSubscribers = [];
}

async function refreshAccessToken() {
  const rToken = getRefreshToken();
  if (!rToken) throw new Error("No refresh token");

  const res = await fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: rToken }),
  });

  if (!res.ok) {
    clearToken();
    throw new Error("Refresh failed");
  }

  const json = await res.json();
  const { access_token, refresh_token: newRefresh } = json.data || {};
  setTokens(access_token, newRefresh || rToken);
  return access_token;
}

async function request(endpoint, options = {}) {
  let token = getToken();

  const makeRequest = async (authToken) => {
    const headers = {
      "Content-Type": "application/json",
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      ...options.headers,
    };

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    if (response.status === 204 || response.status === 205) {
      return null;
    }

    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error(`Request failed with status ${response.status}`);
    }

    if (!response.ok) {
      const errorMessage = extractApiErrorMessage(
        data,
        `Request failed with status ${response.status}`
      );
      const err = new Error(errorMessage);
      err.status = response.status;
      throw err;
    }
    return data;
  };

  try {
    return await makeRequest(token);
  } catch (err) {
    if (err.status === 401 && getRefreshToken()) {
      if (!isRefreshing) {
        isRefreshing = true;
        try {
          const newAccess = await refreshAccessToken();
          isRefreshing = false;
          onRefreshed(newAccess);
          return await makeRequest(newAccess);
        } catch (refreshErr) {
          isRefreshing = false;
          clearToken();
          throw refreshErr;
        }
      }

      // Wait for ongoing refresh
      return new Promise((resolve, reject) => {
        subscribeTokenRefresh((newAccess) => {
          makeRequest(newAccess).then(resolve).catch(reject);
        });
      });
    }
    throw err;
  }
}

/* ----------------------------------------------------------------
   Auth Endpoints
   Backend: app/api/auth.py
   ---------------------------------------------------------------- */

/**
 * POST /api/v1/auth/register
 * Body: { email, password, role }
 * Response: { status: "success", data: { user_id, email, role, ... } }
 */
export async function registerUser({ email, password, role = "viewer" }) {
  return request("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, role }),
  });
}

/**
 * POST /api/v1/auth/login
 * Body: { email, password }
 * Response: { status: "success", data: { access_token, token_type } }
 */
export async function loginUser({ email, password }) {
  const data = await request("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

  // Store both access + refresh tokens (Auth v2)
  const tok = data?.data;
  if (tok?.access_token) {
    setTokens(tok.access_token, tok.refresh_token);
  }

  return data;
}

/**
 * GET /api/v1/auth/me
 * Response: { status: "success", data: { user_id, email, role, is_active, ... } }
 */
export async function getMe() {
  return request("/auth/me");
}

/**
 * POST /api/v1/auth/logout
 * Clears client-side token regardless of server response.
 */
export async function logoutUser() {
  try {
    await request("/auth/logout", { method: "POST" });
  } finally {
    clearToken();
  }
}

/**
 * Google OAuth 2.0 Sign In / Sign Up
 * Sends the ID token received from Google Identity Services.
 */
export async function googleLogin(credential) {
  const data = await request("/auth/google", {
    method: "POST",
    body: JSON.stringify({ credential }),
  });

  const tok = data?.data;
  if (tok?.access_token) {
    setTokens(tok.access_token, tok.refresh_token);
  }

  return data;
}

/* ----------------------------------------------------------------
   Lands Endpoints
   Backend: app/api/lands.py
   ---------------------------------------------------------------- */

/**
 * GET /api/v1/lands
 * Response: { lands: [...], total }
 */
export async function listLands() {
  return request("/lands");
}

/**
 * POST /api/v1/lands/discover
 * Register a new land from a GeoJSON polygon.
 * Body: { name, description, geometry: { type: "Polygon", coordinates: [...] } }
 * Response: { status: "processing", land_id }
 */
export async function discoverLand({ name, description, geometry, metadata_ }) {
  return request("/lands/discover", {
    method: "POST",
    body: JSON.stringify({ name, description, geometry, metadata_ }),
  });
}

/**
 * GET /api/v1/lands/{landId}
 * Response: { land_id, name, description, latitude, longitude, area_hectares, status, boundary_polygon, created_at }
 */
export async function getLandDetail(landId) {
  return request(`/lands/${landId}`);
}

export async function exportLand(landId) {
  const token = getToken();
  const res = await fetch(`${API_BASE}/lands/${landId}/export`, {
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
    },
  });
  if (!res.ok) {
    throw new Error("Failed to export land data");
  }
  return await res.blob();
}

/**
 * GET /api/v1/lands/{landId}/timeseries?metric=climate|water|crops|soil
 * Response: { land_id, metric, points: [{ timestamp, value, payload }] }
 */
export async function getLandTimeseries(landId, metric = "climate", zoneId = null) {
  let url = `/lands/${landId}/timeseries?metric=${metric}`;
  if (zoneId != null && metric === "crops") {
    url += `&zone_id=${zoneId}`;
  }
  return request(url);
}

/**
 * GET /api/v1/lands/{landId}/images?image_type=true_color|ndvi|user_upload
 * Response: { land_id, images: [{ id, date, image_type, image_path, ndvi_mean, cloud_cover_pct }] }
 */
export async function getLandImages(landId, imageType = null) {
  const qs = imageType ? `?image_type=${imageType}` : "";
  return request(`/lands/${landId}/images${qs}`);
}

const imageBlobCache = new Map();
const imageFetchInflight = new Map();
const IMAGE_FETCH_CONCURRENCY = 4;

function normalizeImagePath(imageUrl) {
  if (!imageUrl) return null;
  if (imageUrl.startsWith("blob:")) return imageUrl;
  if (imageUrl.startsWith(API_BASE)) return imageUrl.slice(API_BASE.length);
  if (imageUrl.startsWith("/api/v1")) return imageUrl.slice("/api/v1".length);
  return imageUrl;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchImageBlob(path, attempt = 0) {
  let token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (res.status === 401 && getRefreshToken() && attempt < 2) {
    try {
      if (!isRefreshing) {
        isRefreshing = true;
        token = await refreshAccessToken();
        isRefreshing = false;
        onRefreshed(token);
      } else {
        token = await new Promise((resolve) => {
          subscribeTokenRefresh(resolve);
        });
      }
      return fetchImageBlob(path, attempt + 1);
    } catch {
      clearToken();
      return null;
    }
  }

  if (res.status === 429 && attempt < 4) {
    const retryAfter = Number.parseInt(res.headers.get("Retry-After") || "2", 10);
    await sleep(Math.max(retryAfter, 1) * 1000);
    return fetchImageBlob(path, attempt + 1);
  }

  if (!res.ok) return null;
  return res.blob();
}

/**
 * Fetch a protected image URL with the auth token and return a blob: URL.
 * Browser <img> tags cannot send Authorization headers on their own.
 */
export async function resolveAuthenticatedImageUrl(imageUrl) {
  const path = normalizeImagePath(imageUrl);
  if (!path || path.startsWith("blob:")) return path;

  if (imageBlobCache.has(path)) {
    return imageBlobCache.get(path);
  }
  if (imageFetchInflight.has(path)) {
    return imageFetchInflight.get(path);
  }

  const promise = (async () => {
    const blob = await fetchImageBlob(path);
    if (!blob) return null;
    const blobUrl = URL.createObjectURL(blob);
    imageBlobCache.set(path, blobUrl);
    return blobUrl;
  })().finally(() => {
    imageFetchInflight.delete(path);
  });

  imageFetchInflight.set(path, promise);
  return promise;
}

async function mapWithConcurrency(items, mapper, limit = IMAGE_FETCH_CONCURRENCY) {
  if (!items.length) return [];
  const results = new Array(items.length);
  let nextIndex = 0;

  async function worker() {
    while (nextIndex < items.length) {
      const current = nextIndex;
      nextIndex += 1;
      results[current] = await mapper(items[current], current);
    }
  }

  const workers = Array.from(
    { length: Math.min(limit, items.length) },
    () => worker(),
  );
  await Promise.all(workers);
  return results;
}

export async function resolveLandImageGallery(images = []) {
  return mapWithConcurrency(images || [], async (img) => {
    if (!img?.image_url) return img;
    const blobUrl = await resolveAuthenticatedImageUrl(img.image_url);
    if (!blobUrl) return img;
    return { ...img, image_url: blobUrl, _blobUrl: true, _cached: imageBlobCache.has(normalizeImagePath(img.image_url)) };
  });
}

export function isImageBlobCached(imageUrl) {
  const path = normalizeImagePath(imageUrl);
  return Boolean(path && imageBlobCache.has(path));
}

export function revokeBlobImageUrls(images = []) {
  (images || []).forEach((img) => {
    if (
      img?._blobUrl &&
      !img?._cached &&
      typeof img.image_url === "string" &&
      img.image_url.startsWith("blob:")
    ) {
      URL.revokeObjectURL(img.image_url);
    }
  });
}

/**
 * GET /api/v1/lands/{landId}/crop-zones
 * Response: { land_id, total_zones, zones: [...] }
 */
export async function getCropZones(landId) {
  return request(`/lands/${landId}/crop-zones`);
}

export async function getCropDetection(landId) {
  return request(`/lands/${landId}/crop-detection`);
}

export async function getTrustSummary(landId) {
  return request(`/lands/${landId}/trust-summary`);
}

export async function declarePrimaryCrop(landId, { crop_type, notes }) {
  return request(`/lands/${landId}/declared-crops`, {
    method: "POST",
    body: JSON.stringify({ crop_type, notes }),
  });
}

/**
 * POST /api/v1/lands/{landId}/analyze
 * Triggers a background re-analysis: fetch new satellite images, recompute NDVI.
 * Old images and data are preserved — only new data is appended.
 */
export async function reanalyzeLand(landId, refreshSections = ["environment", "satellite", "crops"]) {
  const refresh = Array.isArray(refreshSections) ? refreshSections.join(",") : refreshSections;
  const qs = refresh ? `?refresh=${encodeURIComponent(refresh)}` : "";
  return request(`/lands/${landId}/analyze${qs}`, { method: "POST" });
}

/**
 * DELETE /api/v1/lands/{landId}
 * Deletes a land and all associated data.
 */
export async function deleteLand(landId) {
  return request(`/lands/${landId}`, { method: "DELETE" });
}

/**
 * PATCH /api/v1/lands/{landId}/settings
 * Update per-land settings (e.g. monitoring_interval_days).
 */
export async function updateLandSettings(landId, settings) {
  return request(`/lands/${landId}/settings`, {
    method: "PATCH",
    body: JSON.stringify(settings),
  });
}

/**
 * GET /api/v1/lands/{landId}/ndvi-comparison
 * Returns weekly NDVI snapshots over time for progress tracking.
 */
export async function getNdviComparison(landId, weeks = 8) {
  return request(`/lands/${landId}/ndvi-comparison?weeks=${weeks}`);
}

/**
 * GET /api/v1/lands/notifications?limit=..
 * Returns recent alerts for the notification bell. Uses LandAlert system.
 */
export async function listNotifications(limit = 10) {
  return request(`/notifications?limit=${limit}`);
}

/**
 * GET /api/v1/notifications/unread-count
 * Returns just the unread badge count (fast poll endpoint).
 */
export async function getUnreadNotificationCount() {
  return request("/notifications/unread-count");
}

/**
 * PATCH /api/v1/notifications/{id}/read
 * Mark a single notification as read.
 */
export async function markNotificationRead(alertId) {
  return request(`/notifications/${alertId}/read`, { method: "PATCH" });
}

/**
 * POST /api/v1/notifications/read-all
 * Mark all notifications as read for the current user.
 */
export async function markAllNotificationsRead() {
  return request("/notifications/read-all", { method: "POST" });
}

/* ----------------------------------------------------------------
   Crop Intelligence Endpoints
   Backend: app/api/crops.py
   ---------------------------------------------------------------- */

/** GET /api/v1/lands/{landId}/crop-health */
export async function getCropHealth(landId) {
  return request(`/lands/${landId}/crop-health`);
}

/** POST /api/v1/lands/{landId}/crop-health/refresh — recompute + persist zone health */
export async function refreshCropHealth(landId) {
  return request(`/lands/${landId}/crop-health/refresh`, { method: "POST" });
}

/** GET /api/v1/lands/{landId}/crop-status */
export async function getCropStatus(landId) {
  return request(`/lands/${landId}/crop-status`);
}

/** GET /api/v1/lands/{landId}/crop-trend?days=90 */
export async function getCropTrend(landId, days = 90) {
  return request(`/lands/${landId}/crop-trend?days=${days}`);
}

/** GET /api/v1/lands/{landId}/harvest-prediction */
export async function getHarvestPrediction(landId) {
  return request(`/lands/${landId}/harvest-prediction`);
}

/* ----------------------------------------------------------------
   Soil Intelligence Endpoints
   Backend: app/api/soil.py
   ---------------------------------------------------------------- */

/** GET /api/v1/lands/{landId}/soil-profile */
export async function getSoilProfile(landId) {
  return request(`/lands/${landId}/soil-profile`);
}

/** POST /api/v1/lands/{landId}/soil-profile/retry */
export async function retrySoilProfile(landId) {
  return request(`/lands/${landId}/soil-profile/retry`, { method: "POST" });
}

/** GET /api/v1/lands/{landId}/soil-suitability */
export async function getSoilSuitability(landId, crop = null) {
  const qs = crop ? `?crop=${crop}` : "";
  return request(`/lands/${landId}/soil-suitability${qs}`);
}

/** GET /api/v1/lands/{landId}/soil-status */
export async function getSoilStatus(landId) {
  return request(`/lands/${landId}/soil-status`);
}

/* ----------------------------------------------------------------
   Admin Activity Logs (only for role=admin)
   ---------------------------------------------------------------- */

/** GET /api/v1/activity-logs */
export async function getActivityLogs(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return request(`/activity-logs${qs ? "?" + qs : ""}`);
}

/* ----------------------------------------------------------------
   Health Check
   Backend: app/api/health.py
   ---------------------------------------------------------------- */

/**
 * GET /api/health
 * Response: { status: "backend running" }
 */
export async function healthCheck() {
  const response = await fetch("/api/health");
  return response.json();
}

/**
 * GET /api/health/db
 * Response: { status: "success"|"error", result|message }
 */
export async function healthCheckDb() {
  const response = await fetch("/api/health/db");
  return response.json();
}

/* ----------------------------------------------------------------
   AI Endpoints
   Backend: app/api/ai.py
   ---------------------------------------------------------------- */

/** GET /ai/keys — list user's API keys (masked) */
export async function getAiApiKeys() {
  return request("/ai/keys");
}

/** POST /ai/keys — add a new API key */
export async function addAiApiKey(apiKey, label = null, provider = "groq") {
  return request("/ai/keys", {
    method: "POST",
    body: JSON.stringify({ api_key: apiKey, label, provider }),
  });
}

/** DELETE /ai/keys/{key_id} — remove an API key */
export async function deleteAiApiKey(keyId) {
  return request(`/ai/keys/${keyId}`, { method: "DELETE" });
}

/** PATCH /ai/keys/{key_id}/toggle — enable/disable a key */
export async function toggleAiApiKey(keyId, isActive) {
  return request(`/ai/keys/${keyId}/toggle`, {
    method: "PATCH",
    body: JSON.stringify({ is_active: isActive }),
  });
}

/** GET /ai/lands/{land_id}/insights — get AI insights */
export async function getAiInsights(landId) {
  return request(`/ai/lands/${landId}/insights`);
}

/** POST /ai/lands/{land_id}/analyze — trigger fresh AI analysis (synchronous) */
export async function triggerAiAnalysis(landId) {
  return request(`/ai/lands/${landId}/analyze`, { method: "POST" });
}

/** POST /ai/lands/{land_id}/analyze-async — trigger background AI analysis (returns 202) */
export async function triggerAiAnalysisAsync(landId) {
  return request(`/ai/lands/${landId}/analyze-async`, { method: "POST" });
}

/** GET /ai/status — AI system health for current user */
export async function getAiStatus() {
  return request("/ai/status");
}
