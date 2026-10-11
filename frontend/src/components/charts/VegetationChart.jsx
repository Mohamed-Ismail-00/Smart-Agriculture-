import { useState, useEffect } from "react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from "recharts";

export default function VegetationChart({ history, subtitle }) {
  // Responsive height for mobile - hooks must be unconditional
  const [chartHeight, setChartHeight] = useState(280);
  const [isSmallScreen, setIsSmallScreen] = useState(false);

  useEffect(() => {
    const update = () => {
      const w = window.innerWidth;
      setIsSmallScreen(w <= 768);
      if (w <= 480) {
        setChartHeight(170);
      } else if (w <= 768) {
        setChartHeight(200);
      } else {
        setChartHeight(280);
      }
    };
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  if (!history || history.length === 0) return null;

  // Format history points for Recharts
  const data = history.map(h => ({
    date: new Date(h.timestamp).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
    NDVI: h.value ? parseFloat(h.value.toFixed(3)) : null,
    DVI: h.payload?.dvi_value ? parseFloat(h.payload.dvi_value.toFixed(3)) : null,
    EVI: h.payload?.evi_value ? parseFloat(h.payload.evi_value.toFixed(3)) : null,
    NDWI: h.payload?.ndwi_value ? parseFloat(h.payload.ndwi_value.toFixed(3)) : null,
    SAVI: h.payload?.savi_value ? parseFloat(h.payload.savi_value.toFixed(3)) : null,
    GNDVI: h.payload?.gndvi_value ? parseFloat(h.payload.gndvi_value.toFixed(3)) : null,
  }));

  return (
    <div className="vegetation-chart" style={{ height: chartHeight }}>
      <h3>
        Vegetation Indices (ML Features)
        {subtitle && <span className="text-caption" style={{ display: "block", fontWeight: 400, marginTop: 2 }}>{subtitle}</span>}
      </h3>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 12, left: -12, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
          <XAxis 
            dataKey="date" 
            stroke="var(--text-secondary)" 
            fontSize={isSmallScreen ? 10 : 11} 
            tickMargin={6} 
            axisLine={false} 
            tickLine={false} 
          />
          <YAxis 
            stroke="var(--text-secondary)" 
            fontSize={isSmallScreen ? 10 : 11} 
            domain={[-0.2, 1]} 
            axisLine={false} 
            tickLine={false} 
          />
          <Tooltip 
            contentStyle={{ 
              backgroundColor: "var(--bg-card)", 
              border: "1px solid var(--border-subtle)", 
              borderRadius: "8px", 
              boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
              fontSize: "12px"
            }}
            itemStyle={{ fontSize: "12px" }}
            labelStyle={{ color: "var(--text-secondary)", marginBottom: "4px", fontWeight: "bold" }}
          />
          <Legend wrapperStyle={{ fontSize: isSmallScreen ? "10px" : "11px", paddingTop: "6px" }} />
          <Line type="monotone" dataKey="NDVI" stroke="#10b981" strokeWidth={2.5} dot={{ r: 2, strokeWidth: 0 }} activeDot={{ r: 4 }} />
          <Line type="monotone" dataKey="DVI" stroke="#ef4444" strokeWidth={1.5} dot={false} activeDot={{ r: 3 }} />
          <Line type="monotone" dataKey="EVI" stroke="#3b82f6" strokeWidth={1.5} dot={false} activeDot={{ r: 3 }} />
          <Line type="monotone" dataKey="NDWI" stroke="#0ea5e9" strokeWidth={1.5} dot={false} activeDot={{ r: 3 }} />
          <Line type="monotone" dataKey="SAVI" stroke="#f59e0b" strokeWidth={1.5} dot={false} activeDot={{ r: 3 }} />
          <Line type="monotone" dataKey="GNDVI" stroke="#8b5cf6" strokeWidth={1.5} dot={false} activeDot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
