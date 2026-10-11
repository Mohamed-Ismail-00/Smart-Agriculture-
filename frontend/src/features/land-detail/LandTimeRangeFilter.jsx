/**
 * LandTimeRangeFilter — date window selector for land detail timeseries
 */

import { useBreakpoint } from "../../hooks/useBreakpoint";
import { TIME_RANGE_OPTIONS, formatMetricCountsBreakdown } from "./landDetailUtils";

export default function LandTimeRangeFilter({
  value,
  onChange,
  counts = {},
  metricBreakdown = {},
  summaryText,
}) {
  const { isDrawer } = useBreakpoint();

  return (
    <div
      className={`land-detail-time-filter${isDrawer ? " land-detail-time-filter--compact" : ""}`}
    >
      <div className="land-detail-time-filter__header">
        <span className="land-detail-time-filter__label">Time range</span>
        {summaryText && (
          <span className="land-detail-time-filter__summary">{summaryText}</span>
        )}
      </div>
      <div
        className="land-detail-time-filter__pills"
        role="group"
        aria-label="Time range filter"
      >
        {TIME_RANGE_OPTIONS.map((opt) => {
          const id = opt.key ?? "all";
          const isActive = value === opt.key || (value == null && opt.key == null);
          const count = counts[id];
          const breakdown = metricBreakdown[id];
          const breakdownText = formatMetricCountsBreakdown(breakdown);
          const label = isDrawer ? opt.shortLabel : opt.label;

          return (
            <button
              key={id}
              type="button"
              className={`land-detail-time-filter__pill${isActive ? " land-detail-time-filter__pill--active" : ""}`}
              onClick={() => onChange(opt.key)}
              aria-pressed={isActive}
              title={breakdownText || undefined}
            >
              <span className="land-detail-time-filter__pill-label">{label}</span>
              {count != null && count > 0 && (
                <span className="land-detail-time-filter__pill-count">{count}</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}