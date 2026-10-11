/**
 * LandMetricsSection — key metrics row for land detail
 */

import { LAND_DETAIL_SOURCES, resolveHarvestDisplay } from "./landDetailUtils";

export default function LandMetricsSection({
  trackedVars,
  derived,
  harvest,
  land,
  harvestTick = 0,
  declaredCrop,
}) {
  const {
    latestCrop,
    latestClimate,
    latestWater,
    primaryCropType,
    hasSyntheticCrops,
  } = derived;

  // harvestTick forces daily/hourly recalc of days-to-harvest from dates
  void harvestTick;
  const harvestDisplay = resolveHarvestDisplay(harvest);

  const sourceParts = [LAND_DETAIL_SOURCES.ndvi];
  if (trackedVars.includes("climate")) sourceParts.push(LAND_DETAIL_SOURCES.climate);
  if (trackedVars.includes("water")) sourceParts.push(LAND_DETAIL_SOURCES.water);
  sourceParts.push(LAND_DETAIL_SOURCES.harvest);

  return (
    <div className="anim-stagger" style={{ "--stagger-index": 1 }}>
      <div className="section-header">
        <h2 className="section-header__title">Key Metrics</h2>
        <span className="text-caption">
          {hasSyntheticCrops ? "Includes synthetic NDVI fallback" : "Selected time range"}
        </span>
      </div>
      <div className="metrics-row">
        <div className="metric-card">
          <div className="metric-card__value" style={{ color: "var(--green-600)" }}>
            {latestCrop ? latestCrop.value?.toFixed(2) : "—"}
          </div>
          <div className="metric-card__label">Current NDVI</div>
          <div className="metric-card__sub">
            {latestCrop?.payload?.growth_stage?.replace("_", " ") || "—"}
            {latestCrop?.payload?.data_source === "synthetic" && " · estimated"}
          </div>
        </div>
        {trackedVars.includes("climate") && (
          <div className="metric-card">
            <div className="metric-card__value">
              {latestClimate?.value != null
                ? latestClimate.payload?.temperature_min_c != null
                  ? `${latestClimate.payload.temperature_min_c}–${latestClimate.value}°C`
                  : `${latestClimate.value}°C`
                : "—"}
            </div>
            <div className="metric-card__label">Temperature Range (estimate)</div>
            <div className="metric-card__sub">
              Mean: {latestClimate?.payload?.temperature_mean_c != null
                ? `${latestClimate.payload.temperature_mean_c}°C`
                : latestClimate?.value != null
                  ? `${latestClimate.value}°C`
                  : "—"}
              {" · "}
              Humidity: {latestClimate?.payload?.humidity_pct ? `${latestClimate.payload.humidity_pct}%` : "—"}
            </div>
          </div>
        )}
        {trackedVars.includes("water") && (
          <div className="metric-card">
            <div className="metric-card__value">
              {latestWater?.payload?.crop_water_requirement_mm && land?.area_hectares
                ? `${(latestWater.payload.crop_water_requirement_mm * land.area_hectares * 10).toFixed(0)}m³`
                : "—"}
            </div>
            <div className="metric-card__label">Est. Water Needed</div>
            <div className="metric-card__sub">
              Based on ET₀ {latestWater?.payload?.crop_water_requirement_mm?.toFixed(1) || 0}mm
            </div>
          </div>
        )}
        <div className="metric-card">
          <div className="metric-card__value">
            {(declaredCrop || primaryCropType)?.split("(")[0]?.trim() || "Unknown"}
          </div>
          <div className="metric-card__label">Primary Crop</div>
          <div className="metric-card__sub">
            {declaredCrop ? "Confirmed by you" : "Estimate"} · Trend: {latestCrop?.payload?.ndvi_trend || "—"}
          </div>
        </div>
        <div className="metric-card">
          <div
            className="metric-card__value"
            style={{
              color:
                harvestDisplay.urgency === "warning"
                  ? "var(--amber-500)"
                  : harvestDisplay.urgency === "healthy"
                    ? "var(--green-600)"
                    : "var(--text-primary)",
            }}
          >
            {harvestDisplay.daysLabel}
          </div>
          <div className="metric-card__label">Days to Harvest</div>
          <div className="metric-card__sub" title={harvest?.note || undefined}>
            {harvestDisplay.available ? harvestDisplay.subLabel : harvestDisplay.subLabel}
            {harvestDisplay.available && " · full NDVI history"}
          </div>
        </div>
      </div>
      <p className="land-detail-section-footer text-caption">
        {sourceParts.join(" · ")}
      </p>
    </div>
  );
}