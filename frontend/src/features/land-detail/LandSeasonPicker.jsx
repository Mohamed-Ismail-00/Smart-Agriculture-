/**
 * LandSeasonPicker — choose the growing season shown on the land detail page.
 * Crops are classified per season, so every section below follows this choice.
 */

import { formatDate } from "./landDetailUtils";

export default function LandSeasonPicker({ seasons, value, onChange }) {
  if (!seasons.length || !value) return null;
  const end = new Date(value.end.getTime() - 86_400_000);

  return (
    <div className="land-detail-season">
      <div className="land-detail-season__header">
        <span className="land-detail-season__label">Season</span>
        <span className="land-detail-season__range">
          {formatDate(value.start)} – {formatDate(end)}
        </span>
      </div>
      <div className="land-detail-season__pills" role="group" aria-label="Growing season">
        {seasons.map((s) => (
          <button
            key={s.key}
            type="button"
            className={`land-detail-season__pill${s.key === value.key ? " land-detail-season__pill--active" : ""}`}
            onClick={() => onChange(s.key)}
            aria-pressed={s.key === value.key}
          >
            {s.label}
            {s.current && <span className="land-detail-season__now">now</span>}
            <span className="land-detail-season__count" title="Satellite observations">{s.count}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
