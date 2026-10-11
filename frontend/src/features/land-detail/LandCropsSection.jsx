/**
 * LandCropsSection — NDVI charts, crop composition, vegetation & crop intelligence
 */

import VegetationChart from "../../components/charts/VegetationChart";
import TrustBadge from "../../components/TrustBadge";
import CropConfirmModal from "./CropConfirmModal";
import {
  LAND_DETAIL_SOURCES,
  computeDaysToHarvest,
  formatHarvestDate,
} from "./landDetailUtils";

function formatYield(tons) {
  if (tons == null || Number.isNaN(tons)) return "—";
  return `${Number(tons).toFixed(1)}t`;
}

export default function LandCropsSection({
  crops,
  cropsByType,
  cropZones,
  primaryZone,
  selectedZoneId,
  onZoneChange,
  hasSyntheticCrops,
  cropHealth,
  harvest,
  land,
  trackedVars,
  handleReanalyze,
  reanalyzing,
  timeRangeSummaryText,
  timeRangeDays,
  cropDetection,
  trustSummary,
  cropConfirmOpen,
  setCropConfirmOpen,
  declaringCrop,
  onDeclareCrop,
}) {
  const ndviTrust = trustSummary?.sections?.find((s) => s.metric === "ndvi");
  const cropTrust = trustSummary?.sections?.find((s) => s.metric === "crop_type");
  const userDesc = land?.description || "";
  const spectralCrop = cropDetection?.detected_crop_type;
  const declaredCrop = cropDetection?.declared_crop;
  const showConflict =
    declaredCrop &&
    spectralCrop &&
    declaredCrop.toLowerCase() !== spectralCrop.toLowerCase();
  const isEstimated = cropDetection?.trust_tier === "estimated";
  const confidenceBand = cropDetection?.confidence_band || "low";
  const requiresConfirmation = cropDetection?.requires_confirmation ?? isEstimated;
  const displayLabel = cropDetection?.display_label || "Suggested";
  const showSuggestionBanner = isEstimated && !declaredCrop;
  const hasNdvi = Object.keys(cropsByType).length > 0;
  const hasCropIntel = trackedVars.includes("ndvi") && (cropHealth || harvest);
  const showZoneSelector = cropZones?.length > 1;
  const selectedZone =
    cropZones?.find((z) => z.zone_id === selectedZoneId) || primaryZone;
  const chartSubtitle = selectedZone
    ? `${selectedZone.crop_type.split("(")[0].trim()} · Zone ${selectedZone.zone_id}`
    : null;

  if (!hasNdvi && !cropZones?.length && !crops?.length && !hasCropIntel) {
    return (
      <div className="land-detail__section anim-stagger" style={{ "--stagger-index": 2 }}>
        <div className="section-header">
          <h2 className="section-header__title">Crop Intelligence</h2>
        </div>
        <div className="card land-detail__empty-card">
          <p className="text-body-sm">
            {timeRangeSummaryText
              ? "No crop observations in the selected period. Try a wider time range."
              : "No crop data available yet."}
          </p>
          <button
            className="btn btn--primary btn--sm"
            onClick={() => handleReanalyze()}
            disabled={reanalyzing}
          >
            {reanalyzing ? "Analyzing..." : "Run Analysis Now"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <>
      {showSuggestionBanner && (
        <div
          className={`land-detail-data-notice land-detail-data-notice--${
            confidenceBand === "high" ? "success" : confidenceBand === "medium" ? "info" : "warning"
          } crop-suggestion-banner${
            confidenceBand === "high" ? " crop-suggestion-banner--likely" : ""
          }${confidenceBand === "low" ? " crop-suggestion-banner--uncertain" : ""} anim-stagger`}
          style={{ "--stagger-index": 1.2 }}
        >
          <span className="land-detail-data-notice__icon" aria-hidden>
            {confidenceBand === "high" ? "✓" : confidenceBand === "medium" ? "🌱" : "?"}
          </span>
          <div className="crop-suggestion-banner__content">
            <div className="crop-suggestion-banner__title-row">
              <strong>
                {displayLabel} crop: {spectralCrop?.split("(")[0].trim()}
              </strong>
              <TrustBadge tier="estimated" />
              {cropDetection?.confidence != null && (
                <span className="text-caption" style={{ fontWeight: 600 }}>
                  {Math.round(cropDetection.confidence * 100)}% fit
                </span>
              )}
            </div>
            <p className="text-body-sm" style={{ margin: 0 }}>
              {cropDetection?.note ||
                "Satellite pattern match — confirm for trusted health and harvest advice."}
            </p>
            <div className="crop-suggestion-banner__actions">
              {confidenceBand === "high" ? (
                <>
                  <button
                    type="button"
                    className="btn btn--primary btn--sm"
                    disabled={declaringCrop}
                    onClick={() =>
                      onDeclareCrop?.({
                        crop_type: spectralCrop,
                        notes: null,
                      })
                    }
                  >
                    {declaringCrop ? "Saving…" : `Accept ${spectralCrop?.split("(")[0].trim()}`}
                  </button>
                  <button
                    type="button"
                    className="btn btn--ghost btn--sm"
                    onClick={() => setCropConfirmOpen?.(true)}
                  >
                    Not right?
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className="btn btn--primary btn--sm"
                  onClick={() => setCropConfirmOpen?.(true)}
                >
                  {requiresConfirmation ? "Confirm crop" : "Review suggestion"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {declaredCrop && (
        <div className="land-detail-data-notice land-detail-data-notice--success anim-stagger" style={{ "--stagger-index": 1.25 }}>
          <TrustBadge tier="verified" />
          <span className="text-body-sm" style={{ marginLeft: "8px" }}>
            Confirmed crop: <strong>{declaredCrop.split("(")[0].trim()}</strong>
          </span>
        </div>
      )}

      {showConflict && (
        <div className="land-detail-data-notice land-detail-data-notice--warning anim-stagger" style={{ "--stagger-index": 1.3 }}>
          <p className="text-body-sm" style={{ margin: 0 }}>
            Your confirmed crop differs from the spectral estimate ({spectralCrop?.split("(")[0].trim()}).
          </p>
        </div>
      )}

      {userDesc && showSuggestionBanner && (
        <div className="land-detail-data-notice land-detail-data-notice--info anim-stagger" style={{ "--stagger-index": 1.35 }}>
          <p className="text-body-sm" style={{ margin: 0 }}>
            You described this land as: <em>{userDesc}</em>
          </p>
        </div>
      )}

      <CropConfirmModal
        open={cropConfirmOpen}
        onClose={() => setCropConfirmOpen?.(false)}
        onConfirm={onDeclareCrop}
        cropDetection={cropDetection}
        declaredCrop={declaredCrop}
        saving={declaringCrop}
      />

      {hasSyntheticCrops && (
        <div className="land-detail-data-notice land-detail-data-notice--warning anim-stagger" style={{ "--stagger-index": 1.5 }}>
          <span className="land-detail-data-notice__icon" aria-hidden>⚠️</span>
          <div>
            <strong>Synthetic NDVI data</strong>
            <p className="text-body-sm">
              Some observations in this period are estimated fallback values, not Sentinel-2 imagery.
              Re-analyze when satellite data is available.
            </p>
          </div>
        </div>
      )}

      {crops && crops.length > 0 && (
        <div className="land-detail__section anim-stagger" style={{ "--stagger-index": 2 }}>
          <div className="section-header land-section-header--mobile">
            <h2 className="section-header__title">Vegetation Indices</h2>
            {showZoneSelector && (
              <select
                className="land-detail-zone-select"
                value={selectedZoneId ?? ""}
                onChange={(e) => onZoneChange(Number(e.target.value))}
                aria-label="Crop zone filter"
              >
                {cropZones.map((zone) => (
                  <option key={zone.zone_id} value={zone.zone_id}>
                    {zone.crop_type.split("(")[0].trim()}
                    {primaryZone?.zone_id === zone.zone_id ? " (primary)" : ""}
                  </option>
                ))}
              </select>
            )}
          </div>
          <VegetationChart history={crops} subtitle={chartSubtitle} />
          <p className="land-detail-section-footer text-caption">
            {LAND_DETAIL_SOURCES.ndvi}
            {selectedZone ? ` · zone ${selectedZone.zone_id}` : ""}
            {ndviTrust && (
              <>
                {" · "}
                <TrustBadge tier={ndviTrust.trust_tier} title={ndviTrust.notes} />
              </>
            )}
          </p>
        </div>
      )}

      {Object.keys(cropsByType).length === 0 && (
        <div className="land-detail__section anim-stagger" style={{ "--stagger-index": 2 }}>
          <div className="section-header land-section-header--mobile">
            <h2 className="section-header__title">NDVI Vegetation Index</h2>
          </div>
          <div className="card land-detail__empty-card">
            <p className="text-body-sm">
              NDVI time-series is being generated or no satellite observations yet for this land.
            </p>
            <button className="btn btn--primary btn--sm" onClick={() => handleReanalyze()} disabled={reanalyzing}>
              {reanalyzing ? "Analyzing..." : "Run Analysis Now"}
            </button>
          </div>
        </div>
      )}

      {Object.entries(cropsByType).map(([cType, cList], index) => {
        const displayList = cList.length > 12 ? cList.slice(-12) : cList;
        const ndviBars = displayList.map((c) => Math.round((c.value || 0) * 100));
        return (
          <div className="land-detail__section anim-stagger" style={{ "--stagger-index": 2 + index * 0.1 }} key={cType}>
            <div className="section-header land-section-header--mobile">
              <h2 className="section-header__title">NDVI — {cType.split("(")[0].trim()}</h2>
              <span className="badge badge--info">{cList.length} obs</span>
            </div>
            <div className="mini-chart">
              <div className="mini-chart__dates">
                <span className="text-caption">
                  {displayList.length > 0 ? new Date(displayList[0].timestamp).toLocaleDateString() : ""}
                </span>
                <span className="text-caption">
                  {displayList.length > 0
                    ? new Date(displayList[displayList.length - 1].timestamp).toLocaleDateString()
                    : ""}
                </span>
              </div>
              <div className="mini-chart__visual">
                {ndviBars.map((h, i) => (
                  <div
                    key={i}
                    className="mini-chart__bar"
                    style={{
                      height: `${Math.max(h, 3)}%`,
                      background: `linear-gradient(0deg, ${
                        h > 70
                          ? "var(--green-200), var(--green-500)"
                          : h > 40
                            ? "var(--warning-border), var(--amber-500)"
                            : "var(--error-border), var(--error)"
                      })`,
                    }}
                    title={`NDVI: ${displayList[i]?.value?.toFixed(2)} — ${displayList[i]?.payload?.growth_stage}`}
                  />
                ))}
              </div>
              {cList.length > 12 && (
                <div className="mini-chart__footnote">
                  Showing latest 12 of {cList.length}
                </div>
              )}
            </div>
          </div>
        );
      })}

      {cropZones && cropZones.length > 0 && (
        <div className="land-detail__section anim-stagger" style={{ "--stagger-index": 2.5 }}>
          <div className="section-header land-section-header--mobile">
            <h2 className="section-header__title">Crop Composition</h2>
            <div className="land-detail__section-title-row">
              {cropTrust && <TrustBadge tier={cropTrust.trust_tier} title={cropTrust.notes} />}
              <span className="badge badge--info">{cropZones.length} zone{cropZones.length !== 1 ? "s" : ""}</span>
            </div>
          </div>
          <div className="insights-grid land-detail-crop-grid">
            {cropZones.map((zone) => {
              const isPrimary = primaryZone && zone.zone_id === primaryZone.zone_id;
              return (
                <div className="card land-detail-crop-card" key={zone.zone_id}>
                  <div className="land-detail-crop-card__header">
                    <div className={`land-detail-crop-card__icon${isPrimary ? " land-detail-crop-card__icon--primary" : ""}`}>
                      {isPrimary ? "🌾" : "🌿"}
                    </div>
                    <div className="land-detail-crop-card__info">
                      <div className="land-detail-crop-card__name">{zone.crop_type.split("(")[0].trim()}</div>
                      <div className="text-caption">
                        {zone.area_hectares ? `${zone.area_hectares.toFixed(1)} ha • ` : ""}
                        {zone.area_pct ? `${zone.area_pct.toFixed(1)}%` : "Secondary crop"}
                      </div>
                    </div>
                  </div>
                  {zone.show_confidence_bar ? (
                    <div className="land-detail-crop-card__confidence">
                      <div className="land-detail-crop-card__confidence-label">
                        <span className="text-caption">Fit score</span>
                        <span className="text-caption" style={{ fontWeight: 600 }}>
                          {zone.avg_confidence ? (zone.avg_confidence * 100).toFixed(0) : 0}%
                        </span>
                      </div>
                      <div className="land-detail-crop-card__confidence-bar">
                        <div
                          style={{
                            width: `${(zone.avg_confidence || 0) * 100}%`,
                            background: isPrimary
                              ? "linear-gradient(90deg, var(--green-400), var(--green-600))"
                              : "linear-gradient(90deg, var(--info), #60a5fa)",
                          }}
                        />
                      </div>
                    </div>
                  ) : (
                    <p className="text-caption" style={{ margin: "0 0 8px" }}>
                      Uncertain match — confirm crop for trusted label
                    </p>
                  )}
                  {zone.ambiguous && (
                    <p className="text-caption land-detail-crop-card__ambiguous">Ambiguous spectral mix</p>
                  )}
                  <div className="land-detail-crop-card__stats">
                    <div>
                      <div className="text-caption">Latest NDVI</div>
                      <div className="land-detail-crop-card__stat-value">{zone.latest_ndvi?.toFixed(2) || "—"}</div>
                    </div>
                    <div>
                      <div className="text-caption">Growth</div>
                      <span className={`badge badge--${isPrimary ? "healthy" : "info"}`}>
                        {zone.latest_growth_stage?.replace("_", " ") || "—"}
                      </span>
                    </div>
                    <div>
                      <div className="text-caption">Est. Yield</div>
                      <div className="land-detail-crop-card__stat-value">
                        {formatYield(zone.estimated_yield_tons)}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          <p className="land-detail-section-footer text-caption">
            {LAND_DETAIL_SOURCES.cropZones}
          </p>
        </div>
      )}

      {hasCropIntel && (
        <div className="land-detail__section anim-stagger" style={{ "--stagger-index": 5 }}>
          <div className="section-header land-section-header--mobile">
            <div className="land-detail__section-title-row">
              <h2 className="section-header__title">Crop Intelligence</h2>
              {cropHealth && (
                <span
                  className={`badge badge--${
                    cropHealth.health_score >= 70 ? "healthy" : cropHealth.health_score >= 40 ? "warning" : "critical"
                  }`}
                >
                  {cropHealth.health_score}/100
                </span>
              )}
            </div>
            <span className="badge badge--info">NDVI-based</span>
          </div>
          {timeRangeDays != null && (
            <div className="land-detail-data-notice land-detail-data-notice--info" style={{ marginBottom: "var(--space-md)" }}>
              <p className="text-body-sm" style={{ margin: 0 }}>
                Harvest &amp; health use {LAND_DETAIL_SOURCES.harvest} — not limited by the time filter above.
              </p>
            </div>
          )}

          {cropHealth?.zones?.length > 0 ? (
            cropHealth.zones.map((zh) => {
              const zhv = harvest?.zones?.find((z) => z.zone_id === zh.zone_id);
              return (
                <div key={zh.zone_id} className="land-detail__zone-block">
                  <h3 className="land-detail__zone-title">{zh.crop_type.split("(")[0].trim()} — Zone</h3>
                  <div className="insights-grid">
                    <div className="insight-card">
                      <div className="insight-card__header">
                        <div className="insight-card__icon" style={{ background: "var(--green-50)", color: "var(--green-600)" }}>
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                          </svg>
                        </div>
                        <span className="insight-card__title">Crop Health</span>
                      </div>
                      <div className="land-detail__health-score">
                        <span className="land-detail__health-score-value">{zh.health_score}</span>
                        <span className="text-caption">/ 100</span>
                        <span
                          className={`badge badge--${
                            zh.health_score >= 70 ? "healthy" : zh.health_score >= 40 ? "warning" : "critical"
                          }`}
                        >
                          {zh.health_status?.replace("_", " ")}
                        </span>
                      </div>
                      <p className="insight-card__body">{zh.advice}</p>
                    </div>
                    {zhv && (
                      <div className="insight-card">
                        <div className="insight-card__header">
                          <div className="insight-card__icon" style={{ background: "var(--warning-light)", color: "var(--amber-500)" }}>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <circle cx="12" cy="12" r="10" />
                              <polyline points="12 6 12 12 16 14" />
                            </svg>
                          </div>
                          <span className="insight-card__title">Harvest Prediction</span>
                        </div>
                        {zhv.prediction_available ? (
                          <>
                            <div style={{ marginBottom: "var(--space-sm)" }}>
                              <div style={{ fontSize: 18, fontWeight: 700 }}>
                                {formatHarvestDate(zhv.estimated_harvest_start)} → {formatHarvestDate(zhv.estimated_harvest_end)}
                              </div>
                              {(() => {
                                const days = computeDaysToHarvest(zhv.estimated_harvest_start) ?? zhv.days_to_harvest;
                                const badge =
                                  days < -14 ? "healthy" : days != null && days <= 14 ? "warning" : "info";
                                const label =
                                  days == null
                                    ? "Estimate unavailable"
                                    : days < -14
                                      ? "Harvested"
                                      : days < 0
                                        ? `${Math.abs(days)}d overdue`
                                        : days === 0
                                          ? "Harvest today"
                                          : `${days} days remaining`;
                                return (
                                  <span className={`badge badge--${badge}`} style={{ marginTop: 4 }}>
                                    {label}
                                  </span>
                                );
                              })()}
                            </div>
                            <p className="insight-card__body">
                              Peak NDVI {zhv.peak_ndvi} on {zhv.peak_date}. Confidence: {zhv.confidence_level}.
                            </p>
                          </>
                        ) : (
                          <div style={{ paddingTop: "8px" }}>
                            <span className="badge badge--neutral">Need more NDVI observations</span>
                            <p className="insight-card__body" style={{ marginTop: "8px" }}>
                              {zhv.note || "Not enough data for prediction."}
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          ) : (
            <div className="insights-grid">
              {cropHealth && (
                <div className="insight-card">
                  <div className="insight-card__header">
                    <div className="insight-card__icon" style={{ background: "var(--green-50)", color: "var(--green-600)" }}>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                      </svg>
                    </div>
                    <span className="insight-card__title">Crop Health</span>
                  </div>
                  <div className="land-detail__health-score">
                    <span className="land-detail__health-score-value">{cropHealth.health_score}</span>
                    <span className="text-caption">/ 100</span>
                    <span
                      className={`badge badge--${
                        cropHealth.health_score >= 70 ? "healthy" : cropHealth.health_score >= 40 ? "warning" : "critical"
                      }`}
                    >
                      {cropHealth.health_status?.replace("_", " ")}
                    </span>
                  </div>
                  <p className="insight-card__body">{cropHealth.advice}</p>
                </div>
              )}
              {harvest && (
                <div className="insight-card">
                  <div className="insight-card__header">
                    <div className="insight-card__icon" style={{ background: "var(--warning-light)", color: "var(--amber-500)" }}>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="12" cy="12" r="10" />
                        <polyline points="12 6 12 12 16 14" />
                      </svg>
                    </div>
                    <span className="insight-card__title">Harvest Prediction</span>
                  </div>
                  {harvest.prediction_available ? (
                    <>
                      <div style={{ marginBottom: "var(--space-sm)" }}>
                        <div style={{ fontSize: 18, fontWeight: 700 }}>
                          {formatHarvestDate(harvest.estimated_harvest_start)} → {formatHarvestDate(harvest.estimated_harvest_end)}
                        </div>
                        {(() => {
                          const days = computeDaysToHarvest(harvest.estimated_harvest_start) ?? harvest.days_to_harvest;
                          const badge =
                            days < -14 ? "healthy" : days != null && days <= 14 ? "warning" : "info";
                          const label =
                            days == null
                              ? "Estimate unavailable"
                              : days < -14
                                ? "Harvested"
                                : days < 0
                                  ? `${Math.abs(days)}d overdue`
                                  : days === 0
                                    ? "Harvest today"
                                    : `${days} days remaining`;
                          return (
                            <span className={`badge badge--${badge}`} style={{ marginTop: 4 }}>
                              {label}
                            </span>
                          );
                        })()}
                      </div>
                      <p className="insight-card__body">
                        Peak NDVI {harvest.peak_ndvi} on {harvest.peak_date}. {harvest.note}
                      </p>
                    </>
                  ) : (
                    <div style={{ paddingTop: "8px" }}>
                      <span className="badge badge--neutral">Need more NDVI observations</span>
                      <p className="insight-card__body" style={{ marginTop: "8px" }}>
                        {harvest.note || "Not enough data for prediction."}
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </>
  );
}