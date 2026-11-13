/**
 * hooks/useDashboard.js — Dashboard aggregate data (web + RN ready)
 */

import { useState, useEffect, useCallback, useMemo } from "react";
import { listLands, getLandTimeseries, healthCheck } from "../services/api";

const MONITORED = ["ready", "active", "active_partial", "completed"];

export function useDashboard() {
  const [lands, setLands] = useState([]);
  const [ndviData, setNdviData] = useState([]);
  const [backendOk, setBackendOk] = useState(null);
  const [loading, setLoading] = useState(true);
  const [chartLandId, setChartLandId] = useState(null);
  const [chartLoading, setChartLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      healthCheck()
        .then((r) => setBackendOk(r.status === "backend running"))
        .catch(() => setBackendOk(false));

      const landsRes = await listLands();
      const allLands = landsRes.lands || [];
      setLands(allLands);
      // Chart the land with the newest satellite observation first.
      const newest = [...allLands].sort((a, b) => (b.latest_ndvi_at || "").localeCompare(a.latest_ndvi_at || ""))[0];
      setChartLandId((current) => current ?? newest?.public_id ?? null);
    } catch {
      // non-critical
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!chartLandId) return undefined;
    let cancelled = false;
    setChartLoading(true);
    getLandTimeseries(chartLandId, "crops")
      .then((r) => !cancelled && setNdviData(r.points || []))
      .catch(() => !cancelled && setNdviData([]))
      .finally(() => !cancelled && setChartLoading(false));
    return () => {
      cancelled = true;
    };
  }, [chartLandId]);

  const stats = useMemo(() => {
    const withNdvi = lands.filter((l) => l.latest_ndvi_at);
    const newest = withNdvi.sort((a, b) => b.latest_ndvi_at.localeCompare(a.latest_ndvi_at))[0] || null;
    return {
      totalArea: lands.reduce((sum, l) => sum + (l.area_hectares || 0), 0),
      readyCount: lands.filter((l) => MONITORED.includes(l.status)).length,
      processingCount: lands.filter((l) => l.status === "processing").length,
      errorCount: lands.filter((l) => l.status === "error").length,
      newestLand: newest,
    };
  }, [lands]);

  return {
    lands,
    ndviData,
    backendOk,
    loading,
    stats,
    chartLandId,
    setChartLandId,
    chartLoading,
    refetch: load,
  };
}
