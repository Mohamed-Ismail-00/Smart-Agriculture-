/**
 * pages/compare/CompareLandsPage.jsx — Side-by-side land comparison
 */

import { useState, useEffect, useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { listLands, getLandDetail, getLandTimeseries, getCropHealth } from "../../services/api";
import { useBreakpoint } from "../../hooks/useBreakpoint";
import "../Pages.css";
import "./CompareLands.css";

const METRICS = [
  { key: "crop", label: "Crop Type" },
  { key: "area", label: "Area" },
  { key: "location", label: "Coordinates" },
  { key: "health", label: "Health Status" },
  { key: "healthScore", label: "AI Health Score" },
  { key: "ndvi", label: "Latest NDVI" },
];

function getDisplayData(data) {
  if (!data?.detail) return null;

  const pts = data.timeseries?.points || [];
  const latestCrop = pts.length > 0 ? pts[pts.length - 1].payload?.crop_type : "Unknown";
  const latestNdvi = pts.length > 0 ? pts[pts.length - 1].value : "—";
  const healthScore = data.health ? data.health.health_score : "—";
  const health = data.health ? data.health.health_status?.replace("_", " ") : "Unknown";

  return {
    name: data.detail.name,
    area: `${data.detail.area_hectares?.toFixed(2) || "—"} ha`,
    location: data.detail.latitude ? `${Number(data.detail.latitude).toFixed(4)}, ${Number(data.detail.longitude).toFixed(4)}` : "—",
    crop: latestCrop,
    ndvi: latestNdvi,
    health,
    healthScore,
    status:
      data.health?.health_score >= 70
        ? "healthy"
        : data.health?.health_score >= 40
          ? "warning"
          : "critical",
  };
}

function formatMetricValue(key, display) {
  if (!display) return "—";
  if (key === "ndvi") {
    return typeof display.ndvi === "number" ? display.ndvi.toFixed(2) : display.ndvi;
  }
  if (key === "healthScore") {
    return `${display.healthScore} / 100`;
  }
  return display[key] ?? "—";
}

function CompareMetricDuels({ displayA, displayB, metrics }) {
  return (
    <div className="compare-metrics-mobile">
      {metrics.map((m) => (
        <div key={m.key} className="compare-metric-duel">
          <div className="compare-metric-duel__label">{m.label}</div>
          <div className="compare-metric-duel__values">
            <div className="compare-metric-duel__side compare-metric-duel__side--a">
              <span className="compare-metric-duel__land compare-metric-duel__land--a">{displayA.name}</span>
              <span className="compare-metric-duel__value">{formatMetricValue(m.key, displayA)}</span>
            </div>
            <div className="compare-metric-duel__divider">vs</div>
            <div className="compare-metric-duel__side compare-metric-duel__side--b">
              <span className="compare-metric-duel__land compare-metric-duel__land--b">{displayB.name}</span>
              <span className="compare-metric-duel__value">{formatMetricValue(m.key, displayB)}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function CompareLandsPage() {
  const { isDrawer, isMobile } = useBreakpoint();
  const isMobileLayout = isDrawer;

  const [lands, setLands] = useState([]);
  const [landAId, setLandAId] = useState("");
  const [landBId, setLandBId] = useState("");
  const [dataA, setDataA] = useState(null);
  const [dataB, setDataB] = useState(null);
  const [loadingA, setLoadingA] = useState(false);
  const [loadingB, setLoadingB] = useState(false);
  const [error, setError] = useState(null);

  const loading = loadingA || loadingB;

  useEffect(() => {
    async function fetchLands() {
      try {
        const res = await listLands();
        if (res.lands) {
          const validLands = res.lands.filter((l) => {
            const s = (l.status || "").toLowerCase();
            return s === "ready" || s === "active" || s === "active_partial" || s === "completed";
          });
          setLands(validLands);
          if (validLands.length > 1) {
            setLandAId(validLands[0].public_id);
            setLandBId(validLands[1].public_id);
          }
        }
      } catch {
        setError("Failed to load lands for comparison.");
      }
    }
    fetchLands();
  }, []);

  useEffect(() => {
    if (!landAId) return;
    let cancelled = false;
    (async () => {
      setLoadingA(true);
      try {
        const [detail, timeseries, health] = await Promise.all([
          getLandDetail(landAId),
          getLandTimeseries(landAId, "crops"),
          getCropHealth(landAId).catch(() => null),
        ]);
        if (!cancelled) setDataA({ detail, timeseries, health });
      } catch (err) {
        console.error("Error fetching Land A:", err);
      } finally {
        if (!cancelled) setLoadingA(false);
      }
    })();
    return () => { cancelled = true; };
  }, [landAId]);

  useEffect(() => {
    if (!landBId) return;
    let cancelled = false;
    (async () => {
      setLoadingB(true);
      try {
        const [detail, timeseries, health] = await Promise.all([
          getLandDetail(landBId),
          getLandTimeseries(landBId, "crops"),
          getCropHealth(landBId).catch(() => null),
        ]);
        if (!cancelled) setDataB({ detail, timeseries, health });
      } catch (err) {
        console.error("Error fetching Land B:", err);
      } finally {
        if (!cancelled) setLoadingB(false);
      }
    })();
    return () => { cancelled = true; };
  }, [landBId]);

  const mergedChartData = useMemo(() => {
    if (!dataA?.timeseries?.points && !dataB?.timeseries?.points) return [];
    const map = new Map();

    const addPoints = (points, key) => {
      if (!points) return;
      points.forEach((p) => {
        const date = p.timestamp.split("T")[0];
        if (!map.has(date)) map.set(date, { date });
        map.get(date)[key] = p.value;
      });
    };

    addPoints(dataA?.timeseries?.points, "ndviA");
    addPoints(dataB?.timeseries?.points, "ndviB");
    return Array.from(map.values()).sort((a, b) => a.date.localeCompare(b.date));
  }, [dataA, dataB]);

  const displayA = getDisplayData(dataA);
  const displayB = getDisplayData(dataB);

  const swapLands = () => {
    setLandAId(landBId);
    setLandBId(landAId);
    setDataA(dataB);
    setDataB(dataA);
  };

  const chartHeight = isMobile ? 320 : isMobileLayout ? 380 : 500;

  return (
    <div className={`anim-fade-in compare-container${isMobileLayout ? " compare-container--mobile" : ""}`}>
      <div className="compare-hero">
        <h1 className="compare-hero__title">Compare Lands</h1>
        <p className="compare-hero__subtitle">
          Side-by-side metrics, health scores, and NDVI performance.
        </p>
      </div>

      {error && (
        <div className="alert alert--error" style={{ marginBottom: "var(--space-md)" }}>
          {error}
        </div>
      )}

      {lands.length < 2 && !error && (
        <div className="compare-empty-state">
          <div className="compare-empty-state__icon">📊</div>
          <h3 className="text-h3">Not enough lands to compare</h3>
          <p className="text-body-sm" style={{ color: "var(--text-secondary)", marginTop: "var(--space-sm)" }}>
            Register at least two lands and wait for processing to complete, then compare them here.
          </p>
        </div>
      )}

      {lands.length > 1 && (
        <div className="compare-selectors-grid">
          <div className="compare-picker compare-picker--a compare-card-a anim-stagger" style={{ "--stagger-index": 0 }}>
            <label className="compare-picker__label compare-picker__label--a" htmlFor="compare-land-a">
              Land A
            </label>
            <select
              id="compare-land-a"
              className="compare-select"
              value={landAId}
              onChange={(e) => setLandAId(e.target.value)}
            >
              {lands.map((l) => (
                <option key={l.public_id || l.land_id} value={l.public_id} disabled={l.public_id === landBId}>{l.name}</option>
              ))}
            </select>
          </div>

          {isMobileLayout ? (
            <button type="button" className="compare-swap-btn" onClick={swapLands} aria-label="Swap lands">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="17 1 21 5 17 9" />
                <path d="M3 11V9a4 4 0 014-4h14" />
                <polyline points="7 23 3 19 7 15" />
                <path d="M21 13v2a4 4 0 01-4 4H3" />
              </svg>
              Swap A ↔ B
            </button>
          ) : (
            <div className="compare-vs-badge anim-stagger" style={{ "--stagger-index": 1 }}>
              VS
            </div>
          )}

          <div className="compare-picker compare-picker--b compare-card-b anim-stagger" style={{ "--stagger-index": 2 }}>
            <label className="compare-picker__label compare-picker__label--b" htmlFor="compare-land-b">
              Land B
            </label>
            <select
              id="compare-land-b"
              className="compare-select"
              value={landBId}
              onChange={(e) => setLandBId(e.target.value)}
            >
              {lands.map((l) => (
                <option key={l.public_id || l.land_id} value={l.public_id} disabled={l.public_id === landAId}>{l.name}</option>
              ))}
            </select>
          </div>
        </div>
      )}

      {loading && (
        <div className="compare-loading">
          <div className="compare-loading__spinner" />
          Loading comparison data…
        </div>
      )}

      {!loading && displayA && displayB && (
        <>
          <div className="compare-summary">
            <div className="compare-summary-card compare-summary-card--a anim-stagger" style={{ "--stagger-index": 2 }}>
              <div className="compare-summary-card__body">
                <div className="compare-summary-card__name compare-summary-card__name--a">{displayA.name}</div>
                <div className="compare-summary-card__meta">{displayA.crop} · {displayA.area}</div>
                <span className={`badge badge--${displayA.status}`}>
                  <span className="badge__dot" />
                  {displayA.health} ({displayA.healthScore}/100)
                </span>
              </div>
            </div>
            <div className="compare-summary-card compare-summary-card--b anim-stagger" style={{ "--stagger-index": 3 }}>
              <div className="compare-summary-card__body">
                <div className="compare-summary-card__name compare-summary-card__name--b">{displayB.name}</div>
                <div className="compare-summary-card__meta">{displayB.crop} · {displayB.area}</div>
                <span className={`badge badge--${displayB.status}`}>
                  <span className="badge__dot" />
                  {displayB.health} ({displayB.healthScore}/100)
                </span>
              </div>
            </div>
          </div>

          <div className="compare-chart-card anim-stagger" style={{ "--stagger-index": 4, minHeight: chartHeight + 100 }}>
            <div className="compare-chart-card__header">
              <h2 className="compare-chart-card__title">NDVI Performance</h2>
              {isMobileLayout && (
                <div className="compare-chart-card__legend">
                  <span className="compare-chart-legend-item">
                    <span className="compare-chart-legend-item__dot" style={{ background: "var(--green-600)" }} />
                    {displayA.name.split(" ")[0]}
                  </span>
                  <span className="compare-chart-legend-item">
                    <span className="compare-chart-legend-item__dot" style={{ background: "var(--amber-500)" }} />
                    {displayB.name.split(" ")[0]}
                  </span>
                </div>
              )}
            </div>
            <div className="compare-chart-card__chart" style={{ height: chartHeight, position: "relative" }}>
              {mergedChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={chartHeight}>
                  <LineChart
                    data={mergedChartData}
                    margin={{
                      top: 10,
                      right: isMobile ? 10 : 30,
                      left: isMobile ? 0 : 8,
                      bottom: 60,
                    }}
                  >
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(0,0,0,0.05)" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: isMobile ? 10 : 12, fill: "#888" }}
                      axisLine={{ stroke: "#e0e0e0" }}
                      tickLine={false}
                      minTickGap={isMobile ? 48 : 40}
                      tickFormatter={(v) => {
                        const d = new Date(v);
                        return `${d.getMonth() + 1}/${d.getDate()}`;
                      }}
                      angle={-35}
                      textAnchor="end"
                      height={50}
                    />
                    <YAxis
                      domain={[(dataMin) => Math.min(0, dataMin), 1]}
                      ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]}
                      tick={{ fontSize: isMobile ? 10 : 12, fill: "#888" }}
                      axisLine={false}
                      tickLine={false}
                      width={isMobile ? 32 : 44}
                      tickFormatter={(v) => v.toFixed(1)}
                    />
                    <Tooltip
                      contentStyle={{
                        borderRadius: 8,
                        border: "1px solid #e0e0e0",
                        boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
                        fontSize: 13,
                      }}
                      formatter={(value, name) => [value?.toFixed(3) ?? "—", name]}
                      labelFormatter={(label) => {
                        const d = new Date(label);
                        return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
                      }}
                    />
                    {!isMobileLayout && (
                      <Legend verticalAlign="top" height={36} iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                    )}
                    <Line
                      type="monotone"
                      name={displayA.name}
                      dataKey="ndviA"
                      stroke="#16a34a"
                      strokeWidth={isMobile ? 2 : 3}
                      dot={false}
                      activeDot={{ r: 5 }}
                      connectNulls={true}
                      isAnimationActive={false}
                    />
                    <Line
                      type="monotone"
                      name={displayB.name}
                      dataKey="ndviB"
                      stroke="#f59e0b"
                      strokeWidth={isMobile ? 2 : 3}
                      dot={false}
                      activeDot={{ r: 5 }}
                      connectNulls={true}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="empty-state" style={{ padding: "var(--space-xl)" }}>
                  <p className="text-body-sm">No NDVI overlap data for these lands yet.</p>
                </div>
              )}
            </div>
          </div>

          <div className="compare-table-wrapper responsive-table-container anim-stagger" style={{ "--stagger-index": 5 }}>
            <table className="premium-compare-table logs-table">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>{displayA.name}</th>
                  <th>{displayB.name}</th>
                </tr>
              </thead>
              <tbody>
                {METRICS.map((m) => (
                  <tr key={m.key}>
                    <td className="metric-label">{m.label}</td>
                    <td className="value-a">{formatMetricValue(m.key, displayA)}</td>
                    <td className="value-b">{formatMetricValue(m.key, displayB)}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <CompareMetricDuels displayA={displayA} displayB={displayB} metrics={METRICS} />
          </div>
        </>
      )}
    </div>
  );
}