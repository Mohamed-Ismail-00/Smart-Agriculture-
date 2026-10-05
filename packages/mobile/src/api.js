/**
 * Mobile API client — mirrors web services/api.js
 */

import * as SecureStore from "expo-secure-store";
import Constants from "expo-constants";

const API_BASE =
  Constants.expoConfig?.extra?.apiBaseUrl || "http://10.0.2.2:8000/api/v1";

const TOKEN_KEY = "agri_token";
const REFRESH_KEY = "agri_refresh_token";

let isRefreshing = false;

async function getToken() {
  return SecureStore.getItemAsync(TOKEN_KEY);
}

async function setToken(t) {
  if (t) await SecureStore.setItemAsync(TOKEN_KEY, t);
}

async function getRefreshToken() {
  return SecureStore.getItemAsync(REFRESH_KEY);
}

async function setRefreshToken(t) {
  if (t) await SecureStore.setItemAsync(REFRESH_KEY, t);
}

async function clearTokens() {
  await SecureStore.deleteItemAsync(TOKEN_KEY);
  await SecureStore.deleteItemAsync(REFRESH_KEY);
}

function unwrap(json) {
  if (json && typeof json === "object" && json.status && json.data !== undefined) {
    return json.data;
  }
  return json;
}

async function refreshAccessToken() {
  const rToken = await getRefreshToken();
  if (!rToken) throw new Error("No refresh token");

  const res = await fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: rToken }),
  });

  if (!res.ok) {
    await clearTokens();
    throw new Error("Refresh failed");
  }

  const json = await res.json();
  const data = unwrap(json);
  await setToken(data.access_token);
  if (data.refresh_token) await setRefreshToken(data.refresh_token);
  return data.access_token;
}

export async function apiRequest(path, options = {}) {
  const makeRequest = async (token) => {
    const headers = {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    };

    const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

    if (res.status === 204 || res.status === 205) return null;

    let json;
    try {
      json = await res.json();
    } catch {
      if (!res.ok) throw new Error(`API ${res.status}`);
      return null;
    }

    if (!res.ok) {
      const detail = json.detail || json.message || `API ${res.status}`;
      const err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      err.response = { status: res.status, data: json };
      throw err;
    }

    return unwrap(json);
  };

  let token = await getToken();
  try {
    return await makeRequest(token);
  } catch (err) {
    if (err.response?.status === 401 && (await getRefreshToken()) && !isRefreshing) {
      isRefreshing = true;
      try {
        const newToken = await refreshAccessToken();
        isRefreshing = false;
        return await makeRequest(newToken);
      } catch (e) {
        isRefreshing = false;
        throw e;
      }
    }
    throw err;
  }
}

export const api = {
  getLandDetail: (id) => apiRequest(`/lands/${id}`),
  getLandTimeseries: (id, metric) => apiRequest(`/lands/${id}/timeseries?metric=${metric}`),
  getLandImages: (id) => apiRequest(`/lands/${id}/images`),
  getCropZones: (id) => apiRequest(`/lands/${id}/crop-zones`),
  getCropHealth: (id) => apiRequest(`/lands/${id}/crop-health`),
  getHarvestPrediction: (id) => apiRequest(`/lands/${id}/harvest-prediction`),
  getAiInsights: (id) => apiRequest(`/ai/lands/${id}/insights`),
  triggerAiAnalysisAsync: (id) => apiRequest(`/ai/lands/${id}/analyze-async`, { method: "POST" }),
  reanalyzeLand: (id) => apiRequest(`/lands/${id}/analyze`, { method: "POST" }),
  deleteLand: (id) => apiRequest(`/lands/${id}`, { method: "DELETE" }),
  discoverLand: (body) =>
    apiRequest("/lands/discover", { method: "POST", body: JSON.stringify(body) }),
};

export async function discoverLand(payload) {
  return api.discoverLand(payload);
}

export async function login(email, password) {
  const data = await apiRequest("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  await setToken(data.access_token);
  if (data.refresh_token) await setRefreshToken(data.refresh_token);
  return data;
}

export async function loginWithGoogle(credential) {
  const data = await apiRequest("/auth/google", {
    method: "POST",
    body: JSON.stringify({ credential }),
  });
  await setToken(data.access_token);
  if (data.refresh_token) await setRefreshToken(data.refresh_token);
  return data;
}

export async function logout() {
  try {
    await apiRequest("/auth/logout", { method: "POST" });
  } catch {
    // ignore
  }
  await clearTokens();
}

export async function getMe() {
  return apiRequest("/auth/me");
}

export async function listLands() {
  return apiRequest("/lands");
}

export async function getLandDetail(id) {
  return api.getLandDetail(id);
}

export async function healthCheck() {
  const base = API_BASE.replace(/\/api\/v1\/?$/, "");
  const res = await fetch(`${base}/api/health`);
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}