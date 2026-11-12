/**
 * LandWeatherSection — season weather and reference crop water need (Open-Meteo estimates),
 * as a short summary and one small daily chart instead of a card per day.
 */

import { ResponsiveContainer, ComposedChart, Line, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from "recharts";
import { formatDate } from "./landDetailUtils";

function Stat({ value, label }) {
  return (
    <div className="land-weather__stat">
      <div className="land-weather__stat-value">{value}</div>
      <div className="text-caption">{label}</div>
    </div>
  );
}

const fmt = (v, digits = 1) => (v == null ? "—" : v.toFixed(digits));

export default function LandWeatherSection({ climate, water, summary, lastWeather }) {
  if (!climate.length && !water.length) {
    return (
      <section className="land-detail__section">
        <div className="section-header">
          <h2 className="section-header__title">Weather and water need</h2>
        </div>
        <div className="card land-detail__empty-card">
          <p className="text-body-sm">No weather records in this season yet.</p>
        </div>
      </section>
    );
  }

  const et0ByDay = new Map(water.map((w) => [w.timestamp.slice(0, 10), w.payload?.crop_water_requirement_mm]));
  const data = climate.map((c) => ({
    date: formatDate(c.timestamp, false),
    temp: c.payload?.temperature_mean_c ?? c.value,
    et0: et0ByDay.get(c.timestamp.slice(0, 10)) ?? null,
  }));

  return (
    <section className="land-detail__section">
      <div className="section-header">
        <h2 className="section-header__title">Weather and water need</h2>
        <span className="badge badge--neutral">{summary.days} days · estimate</span>
      </div>
      <div className="card land-weather">
        <div className="land-weather__stats">
          <Stat value={`${fmt(summary.tempMean)}°C`} label="Mean temperature" />
          <Stat value={`${fmt(summary.tempMin, 0)} to ${fmt(summary.tempMax, 0)}°C`} label="Lowest and highest" />
          <Stat value={`${fmt(summary.rainMm, 0)} mm`} label="Rain" />
          <Stat value={`${fmt(summary.et0Mean)} mm/day`} label="Crop water need (ET₀)" />
          {summary.waterM3 != null && (
            <Stat value={`${Math.round(summary.waterM3).toLocaleString()} m³`} label="Water need in this season" />
          )}
        </div>
        <div className="land-weather__chart">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data} margin={{ top: 5, right: 4, left: -16, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
              <XAxis dataKey="date" stroke="var(--text-secondary)" fontSize={11} minTickGap={24} axisLine={false} tickLine={false} />
              <YAxis yAxisId="t" stroke="var(--text-secondary)" fontSize={11} axisLine={false} tickLine={false} unit="°" />
              <YAxis yAxisId="w" orientation="right" stroke="var(--text-secondary)" fontSize={11} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ borderRadius: 8, fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 11, paddingTop: 6 }} />
              <Bar yAxisId="w" dataKey="et0" name="Water need ET₀ (mm)" fill="#bae6fd" />
              <Line yAxisId="t" type="monotone" dataKey="temp" name="Mean temperature (°C)" stroke="#f59e0b" strokeWidth={2} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <p className="text-caption land-weather__note">
          ET₀ is the reference water need of a crop for that weather, not a measure of irrigation.
          {lastWeather ? ` Data through ${formatDate(lastWeather)}.` : ""}
        </p>
      </div>
    </section>
  );
}
