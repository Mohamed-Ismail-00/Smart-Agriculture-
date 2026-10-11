import React from "react";
import {
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

function ClimateTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;

  const data = payload[0].payload;
  return (
    <div
      style={{
        background: "var(--bg-primary)",
        border: "1px solid var(--border-color)",
        borderRadius: "var(--radius-md)",
        padding: "var(--space-sm)",
        boxShadow: "var(--shadow-md)",
      }}
    >
      <div className="text-caption" style={{ fontWeight: 600, marginBottom: 4 }}>
        {data.fullDate}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: "var(--amber-500)",
          }}
        />
        <span className="text-body-sm">
          <strong>Temperature:</strong> {data.temperature} C
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: "var(--info)",
          }}
        />
        <span className="text-body-sm">
          <strong>Rainfall:</strong> {data.rainfall} mm
        </span>
      </div>
    </div>
  );
}

export default function ClimateChart({ data }) {
  if (!data || data.length === 0) {
    return (
      <div className="empty-state" style={{ padding: "var(--space-xl)" }}>
        <p className="text-body-sm">No climate data available.</p>
      </div>
    );
  }

  const chartData = data.map((d) => {
    const dateObj = new Date(d.timestamp);
    return {
      date: dateObj.toLocaleDateString(undefined, { month: "short", day: "numeric" }),
      fullDate: dateObj.toLocaleDateString(),
      temperature: d.value,
      rainfall: d.payload?.rainfall_mm || 0,
      humidity: d.payload?.humidity_pct || 0,
    };
  });

  return (
    <div style={{ width: "100%", height: "100%", minHeight: 300 }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-color)" />
          <XAxis
            dataKey="date"
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 12, fill: "var(--gray-500)" }}
            dy={10}
          />
          <YAxis
            yAxisId="left"
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 12, fill: "var(--gray-500)" }}
            domain={["auto", "auto"]}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 12, fill: "var(--gray-500)" }}
            domain={[0, "auto"]}
          />
          <Tooltip content={<ClimateTooltip />} />
          <Bar
            yAxisId="right"
            dataKey="rainfall"
            fill="var(--info)"
            radius={[4, 4, 0, 0]}
            maxBarSize={40}
          />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="temperature"
            stroke="var(--amber-500)"
            strokeWidth={3}
            dot={{ r: 4, fill: "var(--amber-500)", strokeWidth: 2, stroke: "var(--bg-primary)" }}
            activeDot={{ r: 6, strokeWidth: 0 }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
