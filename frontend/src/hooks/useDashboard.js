/**
 * hooks/useDashboard.js — Dashboard aggregate data (web + RN ready)
 */

import { useState, useEffect, useCallback, useMemo } from "react";
import {
  listLands,
  getLandTimeseries,
  getCropHealth,
  getHarvestPrediction,
  healthCheck,
} from "../services/api";

export function useDashboard() {
  const [lands, setLands] = useState([]);
  const [ndviData, setNdviData] = useState([]);
  const [cropHealth, setCropHealth] = useState(null);
  const [harvest, setHarvest] = useState(null);
  const [backendOk, setBackendOk] = useState(null);
  const [loading, setLoading] = useState(true);

  const stats = useMemo(() => ({
    totalArea: lands.reduce((sum, l) => sum + (l.area_hectares || 0), 0),
    readyCount: lands.filter((l) => ["ready", "active", "active_partial", "completed"].includes(l.status)).length,
    processingCount: lands.filter((l) => l.status === "processing").length,
    errorCount: lands.filter((l) => l.status === "error").length,
    latestNDVI: ndviData.length > 0 ? ndviData[ndviData.length - 1]?.value : null,
  }), [lands, ndviData]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      healthCheck()
        .then((r) => setBackendOk(r.status === "backend running"))
        .catch(() => setBackendOk(false));

      const landsRes = await listLands();
      const allLands = landsRes.lands || [];
      setLands(allLands);

      if (allLands.length > 0) {
        const primary =
          allLands.find((l) => ["ready", "active", "active_partial", "completed"].includes(l.status)) || allLands[0];
        const pid = primary.public_id;

        getLandTimeseries(pid, "crops")
          .then((r) => setNdviData(r.points || []))
          .catch(() => {});
        getCropHealth(pid).then(setCropHealth).catch(() => {});
        getHarvestPrediction(pid).then(setHarvest).catch(() => {});
      }
    } catch {
      // non-critical
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return {
    lands,
    ndviData,
    cropHealth,
    harvest,
    backendOk,
    loading,
    stats,
    refetch: load,
  };
}