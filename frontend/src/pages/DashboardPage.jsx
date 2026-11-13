/**
 * pages/DashboardPage.jsx — Home dashboard
 * Greeting and the farmers' month, key figures, the season curve of one land, and the land list.
 */

import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Area, CartesianGrid, ComposedChart, Line, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { useAuth } from "../context/AuthContext";
import { useBreakpoint } from "../hooks/useBreakpoint";
import { useDashboard } from "../hooks/useDashboard";
import { PHOTO_CREDITS, currentSeason, farmMonth } from "../utils/farmCalendar";
import "./Dashboard.css";
import "./Home.css";

const HECTARES_PER_FEDDAN = 0.420083;
const MONITORED = ["ready", "active", "active_partial", "completed"];

const feddan = (ha) => (ha || 0) / HECTARES_PER_FEDDAN;
const number = (v, digits = 0) =>
  Number(v).toLocaleString("en-GB", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const shortDate = (ts) => (ts ? new Date(ts).toLocaleDateString("en-GB", { day: "numeric", month: "short" }) : "—");
const longDate = (ts) => (ts ? new Date(ts).toLocaleDateString("en-GB", { day: "numeric", month: "long" }) : "—");

function greeting(date) {
  const h = date.getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

function firstName(email) {
  const name = (email || "").split("@")[0].split(/[._-]/)[0];
  return name ? name.charAt(0).toUpperCase() + name.slice(1) : "farmer";
}

function placeOf(land) {
  const first = (land.description || "").split(/[•,]/)[0].trim();
  return first && first.toLowerCase() !== land.name.toLowerCase() ? first : null;
}

function statusOf(land) {
  if (MONITORED.includes(land.status)) return { label: "Monitored", tone: "ok" };
  if (land.status === "error") return { label: "Needs attention", tone: "bad" };
  return { label: "Processing", tone: "warn" };
}

function ndviTone(v) {
  return v >= 0.5 ? "var(--clover)" : v >= 0.3 ? "var(--leaf)" : "var(--wheat)";
}

function SeasonChart({ points, window: range, height }) {
  const data = points.map((p) => ({
    t: new Date(p.timestamp).getTime(),
    ndvi: p.value != null ? Number(p.value.toFixed(3)) : null,
    ndwi: p.payload?.ndwi_value != null ? Number(p.payload.ndwi_value.toFixed(3)) : null,
  }));
  const peak = data.reduce((best, d) => (d.ndvi != null && (!best || d.ndvi > best.ndvi) ? d : best), null);
  const last = data[data.length - 1];
  const ticks = [];
  for (let d = new Date(range.start); d <= range.end; d.setMonth(d.getMonth() + 1)) ticks.push(d.getTime());

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 10, right: 12, left: -18, bottom: 0 }}>
        <CartesianGrid stroke="var(--line)" vertical={false} />
        <XAxis
          dataKey="t" type="number" scale="time" domain={[range.start.getTime(), range.end.getTime()]}
          ticks={ticks} tickFormatter={(t) => new Date(t).toLocaleDateString("en-GB", { month: "short" })}
          stroke="var(--muted)" fontSize={11} axisLine={false} tickLine={false}
        />
        <YAxis domain={[-0.2, 1]} ticks={[0, 0.25, 0.5, 0.75, 1]} stroke="var(--muted)" fontSize={11} axisLine={false} tickLine={false} />
        <Tooltip
          labelFormatter={(t) => longDate(t)}
          formatter={(v, name) => [v?.toFixed(2), name]}
          contentStyle={{ borderRadius: 8, border: "1px solid var(--line)", fontSize: 12 }}
        />
        <Area type="monotone" dataKey="ndvi" name="NDVI" stroke="none" fill="var(--clover-soft)" fillOpacity={1} connectNulls />
        <Line type="monotone" dataKey="ndwi" name="NDWI" stroke="var(--nile)" strokeWidth={1.5} dot={false} connectNulls />
        <Line type="monotone" dataKey="ndvi" name="NDVI" stroke="var(--clover)" strokeWidth={2.5} dot={false} connectNulls />
        {peak && <ReferenceDot x={peak.t} y={peak.ndvi} r={5} fill="var(--wheat)" stroke="#fff" strokeWidth={2} />}
        {last?.ndvi != null && <ReferenceDot x={last.t} y={last.ndvi} r={4} fill="var(--clover)" stroke="none" />}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { isDrawer } = useBreakpoint();
  const { lands, ndviData, loading, stats, chartLandId, setChartLandId, chartLoading } = useDashboard();

  const today = new Date();
  const month = farmMonth(today);
  const season = currentSeason(today);

  const chartLand = lands.find((l) => l.public_id === chartLandId);
  // The last 12 months: the season just finished and the current one, today at the right edge.
  const chartWindow = useMemo(() => {
    const end = new Date();
    const start = new Date(end.getFullYear() - 1, end.getMonth(), 1);
    return { start, end };
  }, []);
  const chartPoints = ndviData.filter((p) => {
    const t = new Date(p.timestamp);
    return t >= chartWindow.start && t <= chartWindow.end;
  });
  const chartPeak = chartPoints.reduce((best, p) => (p.value != null && (!best || p.value > best.value) ? p : best), null);

  if (loading) {
    return (
      <div className="home anim-fade-in">
        <div className="home-card home-skeleton" style={{ height: 220 }} />
        <div className="home-kpis">{[0, 1, 2, 3].map((i) => <div className="home-card home-skeleton" key={i} style={{ height: 112 }} />)}</div>
      </div>
    );
  }

  const newest = stats.newestLand;
  const area = stats.totalArea;
  const segments = 8;
  const doneSegments = Math.floor(season.share * segments);

  return (
    <div className="home anim-fade-in">
      <section className="home-welcome home-card">
        <div className="home-welcome__text">
          <h1>{greeting(today)}, {firstName(user?.email)}</h1>
          <p>
            {lands.length === 0
              ? "Mark your first field on the map to start watching it from space."
              : `${lands.length} land${lands.length === 1 ? " is" : "s are"} watched by Sentinel-2.${newest ? ` The newest image arrived on ${longDate(newest.latest_ndvi_at)}.` : ""}`}
          </p>
          <div className="home-welcome__actions">
            <button type="button" className="home-btn home-btn--primary" onClick={() => navigate("/lands/new")}>Add a land</button>
            {lands.length > 0 && <button type="button" className="home-btn" onClick={() => navigate("/lands")}>Open my lands</button>}
          </div>
        </div>
        <div className="home-month">
          <img src={month.photo.src} alt={month.photo.alt} />
          <div className="home-month__band">
            <span className="home-month__small">This month in the farmers' calendar</span>
            <span className="home-month__name" lang="ar" dir="rtl">{month.ar}</span>
            {month.proverb && <span className="home-month__proverb" lang="ar" dir="rtl">{month.proverb}</span>}
            <span className="home-month__small">{month.field}</span>
          </div>
        </div>
      </section>

      <section className="home-kpis" aria-label="Key figures">
        <div className="home-card home-kpi">
          <span className="home-label">Lands</span>
          <span className="home-kpi__value">{lands.length}</span>
          <span className="home-kpi__sub">{stats.readyCount === lands.length ? "all being monitored" : `${stats.readyCount} being monitored`}</span>
        </div>
        <div className="home-card home-kpi">
          <span className="home-label">Total area</span>
          <span className="home-kpi__value">{number(feddan(area))} <small>feddan</small></span>
          <span className="home-kpi__sub">{number(area, 1)} hectares</span>
        </div>
        <div className="home-card home-kpi">
          <span className="home-label">Newest greenness</span>
          <span className="home-kpi__value">{newest ? newest.latest_ndvi.toFixed(2) : "—"} <small>NDVI</small></span>
          <span className="home-kpi__sub">{newest ? `${newest.name}, ${shortDate(newest.latest_ndvi_at)}` : "No satellite observations yet"}</span>
          {newest && <div className="home-meter"><i style={{ width: `${Math.max(0, newest.latest_ndvi) * 100}%`, background: ndviTone(newest.latest_ndvi) }} /></div>}
        </div>
        <div className="home-card home-kpi">
          <span className="home-label">Season</span>
          <span className="home-kpi__value">{season.name} <small>{season.label}</small></span>
          <span className="home-kpi__sub">Day {season.day} of {season.length}</span>
          <div className="home-stage" aria-label={`Season progress, day ${season.day} of ${season.length}`}>
            {Array.from({ length: segments }, (_, i) => (
              <i key={i} className={i < doneSegments ? "done" : i === doneSegments ? "now" : ""} />
            ))}
          </div>
        </div>
      </section>

      {lands.length > 0 && (
        <section className="home-row">
          <div className="home-card home-chart">
            <div className="home-card__head">
              <h2>
                Greenness of {chartLand?.name || "your land"}, last 12 months
              </h2>
              <div className="home-chips" role="group" aria-label="Choose a land">
                {lands.map((l) => (
                  <button
                    type="button" key={l.public_id}
                    className={`home-chip${l.public_id === chartLandId ? " home-chip--on" : ""}`}
                    onClick={() => setChartLandId(l.public_id)}
                    aria-pressed={l.public_id === chartLandId}
                  >
                    {l.name}
                  </button>
                ))}
              </div>
            </div>
            {chartLoading ? (
              <div className="home-skeleton" style={{ height: isDrawer ? 200 : 250 }} />
            ) : chartPoints.length > 0 ? (
              <>
                <SeasonChart points={chartPoints} window={chartWindow} height={isDrawer ? 200 : 250} />
                <div className="home-legend">
                  <span><i style={{ background: "var(--clover)" }} />NDVI, greenness</span>
                  <span><i style={{ background: "var(--nile)" }} />NDWI, water in the plant</span>
                  {chartPeak && <span><i style={{ background: "var(--wheat)" }} />Highest {chartPeak.value.toFixed(2)}, {shortDate(chartPeak.timestamp)}</span>}
                </div>
              </>
            ) : (
              <p className="home-empty">No satellite observations for this land in the last 12 months.</p>
            )}
          </div>

          <div className="home-card home-facts">
            <div className="home-card__head"><h2>Your lands at a glance</h2></div>
            <dl>
              <div><dt>Being monitored</dt><dd>{stats.readyCount} of {lands.length}</dd></div>
              <div><dt>Still processing</dt><dd>{stats.processingCount}</dd></div>
              <div><dt>Need attention</dt><dd>{stats.errorCount}</dd></div>
              <div><dt>Newest satellite image</dt><dd>{newest ? shortDate(newest.latest_ndvi_at) : "—"}</dd></div>
              <div><dt>Sentinel-2 passes</dt><dd>every 5 days</dd></div>
            </dl>
          </div>
        </section>
      )}

      {lands.length > 0 && (
        <section className="home-card home-lands">
          <div className="home-card__head">
            <h2>Your lands</h2>
            <button type="button" className="home-btn" onClick={() => navigate("/lands")}>See all</button>
          </div>
          <table>
            <thead>
              <tr><th>Land</th><th>Area</th><th>Newest NDVI</th><th>Image date</th><th>Status</th></tr>
            </thead>
            <tbody>
              {lands.map((l) => {
                const status = statusOf(l);
                const open = () => navigate(`/lands/${l.public_id}`);
                return (
                  <tr key={l.public_id} onClick={open} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && open()}>
                    <td>
                      <div className="home-lands__name">{l.name}</div>
                      {placeOf(l) && <div className="home-lands__place">{placeOf(l)}</div>}
                    </td>
                    <td data-label="Area">{number(feddan(l.area_hectares), feddan(l.area_hectares) < 100 ? 1 : 0)} feddan</td>
                    <td data-label="NDVI">
                      {l.latest_ndvi != null ? (
                        <span className="home-ndvi">
                          <span className="home-meter"><i style={{ width: `${Math.max(0, l.latest_ndvi) * 100}%`, background: ndviTone(l.latest_ndvi) }} /></span>
                          {l.latest_ndvi.toFixed(2)}
                        </span>
                      ) : "—"}
                    </td>
                    <td data-label="Image">{shortDate(l.latest_ndvi_at)}</td>
                    <td><span className={`home-pill home-pill--${status.tone}`}>{status.label}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      )}

      <p className="home-credits">{PHOTO_CREDITS}</p>
    </div>
  );
}
