import React from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

function NDVITooltip({ active, payload }) {
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
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: "var(--green-500)",
          }}
        />
        <span className="text-body-sm">
          <strong>NDVI:</strong> {data.ndvi?.toFixed(2)}
        </span>
      </div>
      <div className="text-caption" style={{ marginTop: 4, color: "var(--gray-500)" }}>
        Stage: {data.stage}
      </div>
    </div>
  );
}

export default function NDVIChart({ data, compact = false }) {
  if (!data || data.length === 0) {
    return (
      <div className="empty-state" style={{ padding: "var(--space-xl)" }}>
        <p className="text-body-sm">No NDVI data available.</p>
      </div>
    );
  }

  const chartData = data.map((d) => {
    const dateObj = new Date(d.timestamp);
    return {
      date: dateObj.toLocaleDateString(undefined, { month: "short", day: "numeric" }),
      fullDate: dateObj.toLocaleDateString(),
      ndvi: d.value,
      stage: d.payload?.growth_stage?.replace("_", " ") || "Unknown",
    };
  });

  const chartMargin = compact
    ? { top: 8, right: 4, left: -16, bottom: 20 }
    : { top: 10, right: 10, left: -20, bottom: 24 };

  return (
    <div className={compact ? "ndvi-chart ndvi-chart--compact" : "ndvi-chart"} style={{ overflow: "hidden" }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={chartMargin}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-color)" />
          <XAxis
            dataKey="date"
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 12, fill: "var(--gray-500)" }}
            dy={10}
          />
          <YAxis
            domain={['auto', 'auto']}
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 12, fill: "var(--gray-500)" }}
          />
          <Tooltip content={<NDVITooltip />} />
          <Line
            type="monotone"
            dataKey="ndvi"
            stroke="var(--green-500)"
            strokeWidth={3}
            dot={{ r: 4, fill: "var(--green-500)", strokeWidth: 2, stroke: "var(--bg-primary)" }}
            activeDot={{ r: 6, strokeWidth: 0 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
