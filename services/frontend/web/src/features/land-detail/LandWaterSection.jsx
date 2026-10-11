/**
 * LandWaterSection — estimated crop water need from Open-Meteo ET₀
 */

import { LAND_DETAIL_SOURCES, resolveWaterRecord } from "./landDetailUtils";

function WaterCard({ record, land }) {
  const data = resolveWaterRecord(record, land);
  const dateLabel = new Date(record.timestamp).toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });

  return (
    <div className="card land-detail-water-card">
      <div className="land-detail-water-card__top">
        <div className="text-overline">{dateLabel}</div>
      </div>

      <div className="land-detail-water-card__hero">
        <span className="land-detail-water-card__icon" aria-hidden>
          💧
        </span>
        <div>
          <div className="land-detail-water-card__metric-value">
            {data.et0Formatted ?? "—"}
          </div>
          <div className="text-caption">Daily crop water need (ET₀)</div>
        </div>
      </div>

      <div className="land-detail-water-card__stats">
        <div className="land-detail-water-card__stat">
          <span className="land-detail-water-card__stat-label">Est. volume</span>
          <span className="land-detail-water-card__stat-value">
            {data.waterFormatted ?? "—"}
            {data.derivedVolume && (
              <span className="land-detail-water-card__hint" title="Computed from ET₀ × land area">
                calc
              </span>
            )}
          </span>
        </div>
        {data.efficiency && (
          <div className="land-detail-water-card__stat">
            <span className="land-detail-water-card__stat-label">Efficiency</span>
            <span className="land-detail-water-card__stat-value">{data.efficiency}</span>
          </div>
        )}
      </div>

      {data.derivedVolume && (
        <p className="land-detail-water-card__footnote text-caption">
          Computed from ET₀ × land area
        </p>
      )}
    </div>
  );
}

export default function LandWaterSection({
  water,
  visibleWater,
  land,
  avgWaterEt0,
  showAllWater,
  setShowAllWater,
  timeRangeSummaryText,
}) {
  if (!water || water.length === 0) {
    return (
      <div className="land-detail__section anim-stagger" style={{ "--stagger-index": 7 }}>
        <div className="section-header land-section-header--mobile">
          <h2 className="section-header__title">Crop Water Need (estimate)</h2>
        </div>
        <div className="card land-detail__empty-card">
          <p className="text-body-sm">
            {timeRangeSummaryText
              ? `No water records in the selected period. Try a wider range.`
              : "No water data tracked for this land."}
          </p>
        </div>
      </div>
    );
  }

  const areaLabel =
    land?.area_hectares != null ? `${Number(land.area_hectares).toFixed(2)} ha` : null;

  return (
    <div className="anim-stagger land-detail__section" style={{ "--stagger-index": 7 }}>
      <div className="section-header land-section-header--mobile">
        <h2 className="section-header__title">Crop Water Need (estimate)</h2>
        <div className="land-detail__badge-row">
          {avgWaterEt0 !== "—" && (
            <span className="badge badge--info">Avg ET₀: {avgWaterEt0} mm/day</span>
          )}
          <span className="badge badge--neutral">{water.length} days</span>
        </div>
      </div>

      {areaLabel && (
        <p className="land-detail-water-intro text-body-sm">
          Daily crop water need is based on reference evapotranspiration (ET₀) for this{" "}
          {areaLabel} field. Volumes are estimated from ET₀ × area. This is not a measurement of
          how much the field was irrigated, and it does not tell when to irrigate.
        </p>
      )}

      <div className="land-detail-water-grid">
        {visibleWater.map((w, i) => (
          <WaterCard key={w.timestamp || i} record={w} land={land} />
        ))}
      </div>

      {water.length > 6 && (
        <div className="land-detail__show-more">
          <button className="btn btn--ghost" onClick={() => setShowAllWater(!showAllWater)}>
            {showAllWater ? "Show Less" : `Show All (${water.length})`}
          </button>
        </div>
      )}

      <p className="land-detail-section-footer text-caption">
        {LAND_DETAIL_SOURCES.water} · ~2 day archive lag
        {water.length > 0 &&
          ` · data through ${new Date(water[water.length - 1].timestamp).toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
            year: "numeric",
          })}`}
      </p>
    </div>
  );
}