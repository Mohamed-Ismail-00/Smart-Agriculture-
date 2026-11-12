/**
 * features/land-detail/landDetailUtils.jsx
 * Shared helpers for the land detail page.
 */

// Nile Delta growing seasons, the same windows as the crop dataset:
// winter 1 Oct – 31 May, summer 1 May – 31 Oct. They overlap in May and October.
function winterSeason(year) {
  return {
    key: `W${year}`,
    label: `Winter ${year}/${String(year + 1).slice(2)}`,
    start: new Date(year, 9, 1),
    end: new Date(year + 1, 5, 1),
  };
}

function summerSeason(year) {
  return {
    key: `S${year}`,
    label: `Summer ${year}`,
    start: new Date(year, 4, 1),
    end: new Date(year, 10, 1),
  };
}

/** Seasons that contain a date (one, or two in May and October). */
export function seasonsOf(date) {
  const d = new Date(date);
  const year = d.getFullYear();
  const month = d.getMonth();
  const seasons = [];
  if (month >= 9) seasons.push(winterSeason(year));
  if (month <= 4) seasons.push(winterSeason(year - 1));
  if (month >= 4 && month <= 9) seasons.push(summerSeason(year));
  return seasons;
}

export function isInSeason(timestamp, season) {
  if (!timestamp || !season) return false;
  const d = new Date(timestamp);
  return d >= season.start && d < season.end;
}

export function filterBySeason(items, season, field = "timestamp") {
  if (!items?.length || !season) return [];
  return items.filter((item) => isInSeason(item[field] || item.timestamp, season));
}

/** Every season with satellite observations, newest first, plus the season running today. */
export function listSeasons(crops, now = new Date()) {
  const byKey = new Map();
  [...crops.map((c) => c.timestamp), now].forEach((ts) => {
    seasonsOf(ts).forEach((s) => byKey.set(s.key, s));
  });
  const current = new Set(seasonsOf(now).map((s) => s.key));
  return [...byKey.values()]
    .map((s) => ({ ...s, current: current.has(s.key), count: filterBySeason(crops, s).length }))
    .sort((a, b) => b.start - a.start);
}

/** Newest season that has satellite observations, else the newest season. */
export function defaultSeasonKey(seasons) {
  return (seasons.find((s) => s.count > 0) || seasons[0])?.key ?? null;
}

export function formatDate(ts, withYear = true) {
  if (!ts) return "—";
  return new Date(ts).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    ...(withYear ? { year: "numeric" } : {}),
  });
}

export function daysSince(ts) {
  if (!ts) return null;
  return Math.floor((Date.now() - new Date(ts).getTime()) / 86_400_000);
}

const HECTARES_PER_FEDDAN = 0.420083;

export function formatArea(hectares) {
  if (hectares == null) return "—";
  const ha = Number(hectares);
  return `${ha.toFixed(2)} ha · ${(ha / HECTARES_PER_FEDDAN).toFixed(1)} feddan`;
}

/** Season summary of daily weather and reference crop water need (ET₀ × area). */
export function summarizeWeather(climate, water, areaHectares) {
  const temps = climate.filter((c) => c.value != null);
  const mins = temps.map((c) => c.payload?.temperature_min_c).filter((v) => v != null);
  const means = temps.map((c) => c.payload?.temperature_mean_c ?? c.value);
  const rain = climate.reduce((sum, c) => sum + (c.payload?.rainfall_mm || 0), 0);
  const et0 = water.map((w) => w.payload?.crop_water_requirement_mm).filter((v) => v != null);
  const et0Total = et0.reduce((sum, v) => sum + v, 0);
  return {
    days: climate.length,
    tempMin: mins.length ? Math.min(...mins) : null,
    tempMax: temps.length ? Math.max(...temps.map((c) => c.value)) : null,
    tempMean: means.length ? means.reduce((a, b) => a + b, 0) / means.length : null,
    rainMm: rain,
    et0Mean: et0.length ? et0Total / et0.length : null,
    et0Total,
    waterM3: areaHectares ? et0Total * areaHectares * 10 : null,
  };
}

export function getLandStatusBadge(status) {
  if (status === "ready" || status === "active") return "healthy";
  if (status === "active_partial") return "warning";
  if (status === "error") return "critical";
  if (status === "processing" || String(status || "").includes("Step")) return "warning";
  return "info";
}

const PIPELINE_WARNING_LABELS = {
  climate_data: "climate data",
  satellite_imagery: "satellite imagery",
  soil_profile: "soil profile",
  crop_detection: "crop detection",
  ai_analysis: "AI insights",
  fatal_error: "unexpected pipeline error",
};

export function formatPipelineWarnings(warnings) {
  const shown = (warnings || []).filter((w) => w !== "ai_analysis");
  if (!shown.length) return null;
  return shown.map((w) => PIPELINE_WARNING_LABELS[w] || w.replace(/_/g, " ")).join(", ");
}

export function formatTaskStatus(status) {
  if (!status || status === "processing") {
    return "Downloading satellite imagery…";
  }
  const text = String(status).replace(/_/g, " ").trim();
  if (!text) return "Processing data…";
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function cropName(crop) {
  return crop ? crop.split("(")[0].trim() : null;
}
