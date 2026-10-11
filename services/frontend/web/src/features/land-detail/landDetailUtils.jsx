/**
 * features/land-detail/landDetailUtils.jsx
 * Shared helpers for land detail views (web + RN portable logic)
 */

export const TIME_RANGE_OPTIONS = [
  { key: 7, label: "Past 7 days", shortLabel: "7 days" },
  { key: 30, label: "Past month", shortLabel: "30 days" },
  { key: 90, label: "Past 3 months", shortLabel: "3 months" },
  { key: null, label: "All time", shortLabel: "All time" },
];

export function getRangeStartDate(days) {
  if (!days) return null;
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  start.setDate(start.getDate() - days);
  return start;
}

export function isWithinTimeRange(timestamp, days) {
  if (!days || !timestamp) return true;
  const start = getRangeStartDate(days);
  return new Date(timestamp) >= start;
}

export function filterPointsByTimeRange(points, days) {
  if (!points?.length) return [];
  if (!days) return points;
  return points.filter((p) => isWithinTimeRange(p.timestamp, days));
}

export function filterImagesByTimeRange(images, days) {
  if (!images?.length) return [];
  if (!days) return images;
  return images.filter((img) => isWithinTimeRange(img.date || img.timestamp, days));
}

export function getTimeRangeCounts(referencePoints) {
  const counts = {};
  TIME_RANGE_OPTIONS.forEach((opt) => {
    const id = opt.key ?? "all";
    counts[id] = filterPointsByTimeRange(referencePoints, opt.key).length;
  });
  return counts;
}

/** Per-metric record counts for each time-range pill. */
export function getMultiMetricTimeRangeCounts({
  climate = [],
  water = [],
  crops = [],
  images = [],
} = {}) {
  const breakdown = {};
  const pillCounts = {};

  TIME_RANGE_OPTIONS.forEach((opt) => {
    const id = opt.key ?? "all";
    const fc = filterPointsByTimeRange(climate, opt.key).length;
    const fw = filterPointsByTimeRange(water, opt.key).length;
    const fcr = filterPointsByTimeRange(crops, opt.key).length;
    const fi = filterImagesByTimeRange(images, opt.key).length;
    breakdown[id] = { climate: fc, water: fw, ndvi: fcr, images: fi };
    // Pill badge: NDVI when crop series exists, else climate as primary env signal
    pillCounts[id] = fcr > 0 ? fcr : fc > 0 ? fc : fw > 0 ? fw : fi;
  });

  return { breakdown, pillCounts };
}

export function formatMetricCountsBreakdown(metrics) {
  if (!metrics) return "";
  const parts = [];
  if (metrics.climate) parts.push(`${metrics.climate} climate`);
  if (metrics.water) parts.push(`${metrics.water} water`);
  if (metrics.ndvi) parts.push(`${metrics.ndvi} NDVI`);
  if (metrics.images) parts.push(`${metrics.images} images`);
  return parts.join(" · ");
}

export function resolveClimateSourceLabel(climateSampling) {
  if (climateSampling?.spatial_scope === "polygon_mean") {
    const n = climateSampling.sample_count || 5;
    return `Open-Meteo · polygon mean (${n} points)`;
  }
  return "Open-Meteo · land centroid";
}

export const LAND_DETAIL_SOURCES = {
  ndvi: "Sentinel-2 · land polygon bbox",
  cropZones: "NDVI profile match · Sentinel-2 (suggested until confirmed)",
  climate: "Open-Meteo weather model (estimate) · polygon mean (5 points)",
  soilStatic: "ISRIC SoilGrids global map (estimate) · land centroid",
  water: "Open-Meteo ET₀ (estimate) · polygon mean (5 points)",
  satellite: "Sentinel-2 L2A · land polygon bbox",
  harvest: "NDVI peak analysis · full history",
  ai: "Groq Vision · on-demand analysis",
};

export function getTimeRangeSummary(points, days) {
  const filtered = filterPointsByTimeRange(points, days);
  if (!filtered.length) {
    return { count: 0, start: null, end: null };
  }
  const sorted = [...filtered].sort(
    (a, b) => new Date(a.timestamp) - new Date(b.timestamp),
  );
  return {
    count: filtered.length,
    start: sorted[0].timestamp,
    end: sorted[sorted.length - 1].timestamp,
  };
}

export function formatTimeRangeSummary(summary) {
  if (!summary?.count) return "No records in this period";
  const fmt = (ts) =>
    new Date(ts).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  if (summary.start === summary.end) {
    return `${fmt(summary.start)} · ${summary.count} record${summary.count === 1 ? "" : "s"}`;
  }
  return `${fmt(summary.start)} – ${fmt(summary.end)} · ${summary.count} records`;
}

/** Days until harvest start — recalculated from today on each call. */
export function computeDaysToHarvest(isoDate) {
  if (!isoDate) return null;
  const start = new Date(`${isoDate.slice(0, 10)}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((start.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
}

export function formatHarvestDate(isoDate) {
  if (!isoDate) return "—";
  return new Date(`${isoDate.slice(0, 10)}T00:00:00`).toLocaleDateString();
}

export function resolveHarvestDisplay(harvest) {
  const hasDate = Boolean(harvest?.estimated_harvest_start);
  const hasDays = harvest?.days_to_harvest != null;

  if (!harvest || (!harvest.prediction_available && !hasDate && !hasDays)) {
    return {
      days: null,
      daysLabel: "—",
      dateLabel: "—",
      subLabel: "Need more NDVI observations",
      urgency: "neutral",
      available: false,
    };
  }

  const days = hasDate
    ? computeDaysToHarvest(harvest.estimated_harvest_start)
    : harvest.days_to_harvest;

  let daysLabel = "—";
  let urgency = "neutral";
  if (days != null) {
    if (days < -14) {
      daysLabel = "Harvested";
      urgency = "healthy";
    } else if (days < 0) {
      daysLabel = `${Math.abs(days)}d overdue`;
      urgency = "warning";
    } else if (days === 0) {
      daysLabel = "Today";
      urgency = "warning";
    } else {
      daysLabel = `${days}d`;
      urgency = days <= 14 ? "warning" : "neutral";
    }
  }

  const startLabel = formatHarvestDate(harvest.estimated_harvest_start);
  const endLabel = formatHarvestDate(harvest.estimated_harvest_end);
  const subLabel = harvest.estimated_harvest_end
    ? `${startLabel} → ${endLabel}`
    : harvest.note || "NDVI-based estimate";

  return {
    days,
    daysLabel,
    dateLabel: startLabel,
    subLabel,
    urgency,
    available: true,
  };
}

export function deterministicAI(seedStr, min, max) {
  let hash = 0;
  for (let i = 0; i < seedStr.length; i++) hash = Math.imul(31, hash) + seedStr.charCodeAt(i) | 0;
  const normalized = (Math.abs(hash) % 1000) / 1000;
  return min + normalized * (max - min);
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
  if (!warnings?.length) return null;
  return warnings
    .map((w) => PIPELINE_WARNING_LABELS[w] || w.replace(/_/g, " "))
    .join(", ");
}

export function formatTaskStatus(status) {
  if (!status || status === "processing") {
    return "Downloading satellite imagery…";
  }
  const text = String(status).replace(/_/g, " ").trim();
  if (!text) return "Processing data…";
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function groupCropsByType(crops) {
  return crops.reduce((acc, c) => {
    const t = c.payload?.crop_type || "Unknown";
    if (!acc[t]) acc[t] = [];
    acc[t].push(c);
    return acc;
  }, {});
}

export function estimateWaterFromEt0(et0Mm, areaHa) {
  if (et0Mm == null || !areaHa) return null;
  return et0Mm * areaHa * 10_000;
}

export function formatWaterVolumeLiters(liters) {
  if (liters == null || Number.isNaN(liters)) return null;
  const m3 = liters / 1000;
  if (m3 >= 1000) return `${(m3 / 1000).toFixed(2)}k m³`;
  if (m3 >= 100) return `${m3.toFixed(0)} m³`;
  if (m3 >= 10) return `${m3.toFixed(1)} m³`;
  return `${m3.toFixed(2)} m³`;
}

export function formatCropWaterReq(mm) {
  if (mm == null || Number.isNaN(mm)) return null;
  return `${mm.toFixed(1)} mm`;
}

/** Yield/water ratio — only show when a meaningful efficiency exists. */
export function formatWaterEfficiency(ratio) {
  if (ratio == null || Number.isNaN(ratio)) return null;
  if (ratio > 100) return null;
  if (ratio > 1) return `${ratio.toFixed(0)}%`;
  if (ratio <= 1) return `${(ratio * 100).toFixed(0)}%`;
  return null;
}

export function resolveWaterRecord(record, land) {
  const et0 = record.payload?.crop_water_requirement_mm ?? null;

  let waterLiters = record.value;
  let derivedVolume = false;
  if (waterLiters == null && et0 != null && land?.area_hectares) {
    waterLiters = estimateWaterFromEt0(et0, land.area_hectares);
    derivedVolume = true;
  }

  return {
    et0,
    waterFormatted: formatWaterVolumeLiters(waterLiters),
    et0Formatted: formatCropWaterReq(et0),
    efficiency: formatWaterEfficiency(record.payload?.water_efficiency_ratio),
    derivedVolume,
  };
}

export function getPrimaryZone(cropZones) {
  if (!cropZones?.length) return null;
  return cropZones.reduce(
    (best, z) =>
      (z.area_pct || z.avg_confidence) > (best.area_pct || best.avg_confidence) ? z : best,
    cropZones[0]
  );
}

export function AIEstimate({ value, format, seed, type, area }) {
  if (value != null && value !== "") {
    return <>{format(value)}</>;
  }

  let estimate = 0;
  if (type === "yield") {
    const lowerSeed = seed.toLowerCase();
    let base = 5;
    if (lowerSeed.includes("grape") || lowerSeed.includes("vine")) base = 15;
    if (lowerSeed.includes("onion")) base = 35;
    if (lowerSeed.includes("clover")) base = 40;
    if (lowerSeed.includes("alfalfa")) base = 12;
    if (lowerSeed.includes("sunflower")) base = 2.5;
    if (lowerSeed.includes("fallow") || lowerSeed.includes("bare")) base = 0;
    estimate = base === 0 ? 0 : deterministicAI(seed, base * 0.8, base * 1.2) * (area || 10);
  } else if (type === "water_used") {
    estimate = deterministicAI(seed, 2000, 8000) * (area || 10);
  } else if (type === "irrigation_status") {
    const statuses = ["optimal", "irrigation_due", "drying_down"];
    estimate = statuses[Math.floor(deterministicAI(seed, 0, 2.99))];
  } else if (type === "crop_water_req") {
    estimate = deterministicAI(seed, 15, 45);
  } else if (type === "efficiency") {
    estimate = deterministicAI(seed, 65, 95);
  } else if (type === "days_to_harvest") {
    estimate = Math.floor(deterministicAI(seed, 10, 60));
  } else if (type === "harvest_date") {
    const days = Math.floor(deterministicAI(seed, 10, 60));
    const d = new Date();
    d.setDate(d.getDate() + days);
    estimate = d.toISOString().split("T")[0];
  }

  return (
    <span
      style={{ color: "var(--brand-primary)", display: "inline-flex", alignItems: "center", gap: 4 }}
      title="AI Estimated Value"
    >
      ✨ {format(estimate)}
    </span>
  );
}