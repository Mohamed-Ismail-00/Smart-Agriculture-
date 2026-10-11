/**
 * LandEnvironmentSection — SoilGrids soil profile and Open-Meteo climate history
 */

import { useState } from "react";
import { LAND_DETAIL_SOURCES, resolveClimateSourceLabel } from "./landDetailUtils";

function findProperty(profile, name) {
  return profile?.properties?.find((p) => p.name.toLowerCase().includes(name.toLowerCase()));
}

function formatProfileValue(prop) {
  if (!prop || prop.topsoil_value == null) return "—";
  return `${prop.topsoil_value}${prop.unit ? ` ${prop.unit}` : ""}`;
}

export default function LandEnvironmentSection({
  trackedVars,
  climate,
  soilProfile,
  visibleClimate,
  avgClimateTemp,
  showAllClimate,
  setShowAllClimate,
  timeRangeSummaryText,
  climateSampling,
  areaHectares,
  onRetrySoilProfile,
  soilRetryLoading,
}) {
  const [soilRetryError, setSoilRetryError] = useState(null);

  const hasClimate = trackedVars.includes("climate") && climate && climate.length > 0;
  const hasStaticProfile = soilProfile?.profile_available;
  const soilUnavailable =
    !hasStaticProfile &&
    (soilProfile?.retry_available ||
      ["timeout", "error", "empty"].includes(soilProfile?.fetch_status));
  const phProp = findProperty(soilProfile, "ph");
  const socProp = findProperty(soilProfile, "soc") || findProperty(soilProfile, "organic");
  const clayProp = findProperty(soilProfile, "clay");
  const sandProp = findProperty(soilProfile, "sand");

  const climateSourceLabel = resolveClimateSourceLabel(climateSampling);
  const showLargeFieldWarning =
    climateSampling?.large_field_warning ||
    (areaHectares > 50 && climateSampling?.high_spread);

  const climateThroughDate =
    climate?.length > 0
      ? new Date(climate[climate.length - 1].timestamp).toLocaleDateString(undefined, {
          month: "short",
          day: "numeric",
          year: "numeric",
        })
      : null;

  async function handleSoilRetry() {
    if (!onRetrySoilProfile) return;
    setSoilRetryError(null);
    try {
      await onRetrySoilProfile();
    } catch (err) {
      setSoilRetryError(err?.message || "Soil profile retry failed");
    }
  }

  if (!hasClimate && !hasStaticProfile && !soilUnavailable) {
    return (
      <div className="land-detail__section">
        <div className="card land-detail__empty-card">
          <p className="text-body-sm">
            {timeRangeSummaryText
              ? `No soil or climate data in the selected period (${timeRangeSummaryText}). Try a wider range.`
              : "No soil or climate data tracked for this land."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <>
      {soilUnavailable && (
        <div className="land-detail__section anim-stagger" style={{ "--stagger-index": 3.4 }}>
          <div className="section-header land-section-header--mobile">
            <h2 className="section-header__title">Soil Profile</h2>
            <span className="badge badge--warning">Unavailable</span>
          </div>
          <div className="card land-detail__empty-card">
            <p className="text-body-sm">
              {soilProfile?.fetch_status === "timeout"
                ? "ISRIC SoilGrids timed out during the initial fetch."
                : soilProfile?.fetch_status === "error"
                  ? "ISRIC SoilGrids could not be reached."
                  : "Soil profile has not been fetched yet."}
            </p>
            {soilProfile?.last_fetch_error && (
              <p className="text-caption" style={{ marginTop: 8 }}>
                {soilProfile.last_fetch_error}
              </p>
            )}
            {onRetrySoilProfile && (
              <button
                type="button"
                className="btn btn--primary"
                style={{ marginTop: 12 }}
                onClick={handleSoilRetry}
                disabled={soilRetryLoading}
              >
                {soilRetryLoading ? "Retrying…" : "Retry soil profile fetch"}
              </button>
            )}
            {soilRetryError && (
              <p className="text-caption" style={{ marginTop: 8, color: "var(--danger)" }}>
                {soilRetryError}
              </p>
            )}
            <p className="land-detail-section-footer text-caption">
              {LAND_DETAIL_SOURCES.soilStatic}
            </p>
          </div>
        </div>
      )}

      {hasStaticProfile && (
        <div className="land-detail__section anim-stagger" style={{ "--stagger-index": 3.5 }}>
          <div className="section-header land-section-header--mobile">
            <h2 className="section-header__title">Soil Profile</h2>
            <span className="badge badge--info">SoilGrids · estimate</span>
          </div>
          <div className="card land-detail-soil-profile">
            <div className="land-detail-soil-profile__header">
              <span className="land-detail-soil-profile__texture">
                {soilProfile.texture_class || "Texture unknown"}
              </span>
              {soilProfile.fetched_at && (
                <span className="text-caption">
                  Fetched {new Date(soilProfile.fetched_at).toLocaleDateString()}
                </span>
              )}
            </div>
            <div className="land-detail-soil-profile__grid">
              <div className="land-detail-soil-profile__item">
                <span className="text-caption">pH (0–5 cm)</span>
                <span className="land-detail-soil-profile__value">{formatProfileValue(phProp)}</span>
                {phProp?.classification && (
                  <span className="badge badge--neutral">{phProp.classification}</span>
                )}
              </div>
              <div className="land-detail-soil-profile__item">
                <span className="text-caption">Organic carbon</span>
                <span className="land-detail-soil-profile__value">{formatProfileValue(socProp)}</span>
              </div>
              <div className="land-detail-soil-profile__item">
                <span className="text-caption">Clay</span>
                <span className="land-detail-soil-profile__value">{formatProfileValue(clayProp)}</span>
              </div>
              <div className="land-detail-soil-profile__item">
                <span className="text-caption">Sand</span>
                <span className="land-detail-soil-profile__value">{formatProfileValue(sandProp)}</span>
              </div>
            </div>
            <p className="land-detail-section-footer text-caption">
              {LAND_DETAIL_SOURCES.soilStatic}
            </p>
          </div>
        </div>
      )}

      {hasClimate && (
        <div className="land-detail__section anim-stagger" style={{ "--stagger-index": 6 }}>
          <div className="section-header land-section-header--mobile">
            <h2 className="section-header__title">Climate History (estimate)</h2>
            <div className="land-detail__badge-row">
              <span className="badge badge--info">Avg mean: {avgClimateTemp}°C</span>
              <span className="badge badge--neutral">{climate.length} records</span>
            </div>
          </div>
          {showLargeFieldWarning && (
            <div className="card" style={{ marginBottom: 12, padding: "10px 14px", borderLeft: "3px solid var(--warning)" }}>
              <p className="text-body-sm" style={{ margin: 0 }}>
                Large field ({Math.round(areaHectares)} ha) with notable temperature variation across
                corners ({climateSampling?.temp_spread_c ?? "—"}°C). Polygon mean may not represent
                all micro-climates — confirm with local readings.
              </p>
            </div>
          )}
          <div className="climate-grid">
            {visibleClimate.map((c, i) => {
              const isRaining = c.payload?.rainfall_mm > 0;
              const isCloudy = c.payload?.humidity_pct > 75;
              const weatherIcon = isRaining ? "🌧️" : isCloudy ? "☁️" : "☀️";
              return (
                <div className="climate-card" key={i}>
                  <div className="date">
                    {new Date(c.timestamp).toLocaleDateString(undefined, {
                      weekday: "short",
                      month: "short",
                      day: "numeric",
                    })}
                  </div>
                  <div className="weather-icon">{weatherIcon}</div>
                  <div className="temp">
                    {c.payload?.temperature_min_c != null && c.value != null
                      ? `${c.payload.temperature_min_c}–${c.value}`
                      : c.value}
                    °C
                  </div>
                  <div className="text-caption" style={{ marginTop: 2 }}>
                    {c.payload?.temperature_mean_c != null
                      ? `mean ${c.payload.temperature_mean_c}°C`
                      : "max temp"}
                  </div>
                  <div className="meta">
                    <span className="badge badge--info" style={{ justifyContent: "center", fontSize: 10, padding: "2px 6px" }}>
                      💧 {c.payload?.humidity_pct || 0}%
                    </span>
                    {isRaining && (
                      <span className="badge badge--warning" style={{ justifyContent: "center", fontSize: 10, padding: "2px 6px" }}>
                        ☔ {c.payload?.rainfall_mm} mm
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          {climate.length > 6 && (
            <div className="land-detail__show-more">
              <button className="btn btn--ghost" onClick={() => setShowAllClimate(!showAllClimate)}>
                {showAllClimate ? "Show Less" : `Show All (${climate.length})`}
              </button>
            </div>
          )}
          <p className="land-detail-section-footer text-caption">
            {climateSourceLabel} · ~2 day archive lag
            {climateThroughDate ? ` · data through ${climateThroughDate}` : ""}
            {climateSampling?.temp_spread_c != null && climateSampling.temp_spread_c > 3
              ? ` · corner spread ${climateSampling.temp_spread_c}°C`
              : ""}
          </p>
        </div>
      )}
    </>
  );
}