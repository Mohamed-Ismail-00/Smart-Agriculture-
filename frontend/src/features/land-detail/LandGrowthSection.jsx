/**
 * LandGrowthSection — the season's crop curve: NDVI (greenness) and NDWI (water in the plant).
 * This is the same series the crop model reads.
 */

import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from "recharts";
import { useBreakpoint } from "../../hooks/useBreakpoint";
import { formatDate } from "./landDetailUtils";

export default function LandGrowthSection({ points, seasonLabel, hasSynthetic, onReanalyze, reanalyzing }) {
  const { isMobile } = useBreakpoint();
  const data = points.map((p) => ({
    date: formatDate(p.timestamp, false),
    NDVI: p.value != null ? Number(p.value.toFixed(3)) : null,
    NDWI: p.payload?.ndwi_value != null ? Number(p.payload.ndwi_value.toFixed(3)) : null,
  }));
  const latest = points.length ? points[points.length - 1] : null;
  const peak = points.reduce((best, p) => (p.value != null && (!best || p.value > best.value) ? p : best), null);

  return (
    <section className="land-detail__section">
      <div className="section-header">
        <h2 className="section-header__title">Crop growth</h2>
        <span className="badge badge--neutral">{points.length} observations</span>
      </div>

      {points.length === 0 ? (
        <div className="card land-detail__empty-card">
          <p className="text-body-sm">No satellite observations in {seasonLabel} yet.</p>
          <button className="btn btn--primary btn--sm" onClick={() => onReanalyze()} disabled={reanalyzing}>
            {reanalyzing ? "Updating…" : "Update now"}
          </button>
        </div>
      ) : (
        <div className="card land-growth">
          <div className="land-growth__stats">
            <div>
              <div className="land-growth__stat-value">{latest.value?.toFixed(2) ?? "—"}</div>
              <div className="text-caption">NDVI on {formatDate(latest.timestamp)}</div>
            </div>
            {peak && (
              <div>
                <div className="land-growth__stat-value">{peak.value.toFixed(2)}</div>
                <div className="text-caption">Season peak, {formatDate(peak.timestamp)}</div>
              </div>
            )}
          </div>
          <div className="land-growth__chart" style={{ height: isMobile ? 200 : 260 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data} margin={{ top: 5, right: 12, left: -12, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
                <XAxis dataKey="date" stroke="var(--text-secondary)" fontSize={11} tickMargin={6} axisLine={false} tickLine={false} />
                <YAxis stroke="var(--text-secondary)" fontSize={11} domain={[-0.2, 1]} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ borderRadius: 8, fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 11, paddingTop: 6 }} />
                <Line type="monotone" dataKey="NDVI" name="NDVI (greenness)" stroke="#10b981" strokeWidth={2.5} dot={{ r: 2 }} connectNulls />
                <Line type="monotone" dataKey="NDWI" name="NDWI (water in the plant)" stroke="#0ea5e9" strokeWidth={1.5} dot={false} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          </div>
          {hasSynthetic && (
            <p className="text-caption land-growth__warning">
              Some points in this season are estimated fallback values, not satellite images.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
