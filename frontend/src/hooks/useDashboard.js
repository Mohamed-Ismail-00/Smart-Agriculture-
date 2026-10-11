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
  getAiInsights,
  triggerAiAnalysis,
} from "../services/api";

export function useDashboard() {
  const [lands, setLands] = useState([]);
  const [ndviData, setNdviData] = useState([]);
  const [cropHealth, setCropHealth] = useState(null);
  const [harvest, setHarvest] = useState(null);
  const [backendOk, setBackendOk] = useState(null);
  const [loading, setLoading] = useState(true);
  const [aiInsights, setAiInsights] = useState([]);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState(null);
  const [analyzingLandId, setAnalyzingLandId] = useState(null);

  const preferredLand = useMemo(
    () => lands.find((l) => ["ready", "active", "active_partial", "completed"].includes(l.status)) || lands[0] || null,
    [lands]
  );

  const preferredLandId = preferredLand?.public_id ?? null;

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

        setAiLoading(true);
        setAiError(null);
        getAiInsights(pid)
          .then((r) => setAiInsights(r.insights || []))
          .catch((err) => {
            if (err.response?.status === 429) {
              setAiError("AI Quota Finished. Please try again later or upgrade your plan.");
            } else {
              setAiError("Could not load AI Insights right now.");
            }
            setAiInsights([]);
          })
          .finally(() => setAiLoading(false));
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

  const triggerAnalysis = useCallback(async () => {
    if (!preferredLandId) return;
    setAnalyzingLandId(preferredLandId);
    setAiError(null);
    try {
      await triggerAiAnalysis(preferredLandId);
      setTimeout(async () => {
        try {
          const res = await getAiInsights(preferredLandId);
          setAiInsights(res.insights || []);
          setAiError(null);
        } catch (err) {
          if (err.response?.status === 429) {
            setAiError("AI Quota Finished. Please try again later.");
          } else {
            setAiError("Failed to fetch new AI Insights.");
          }
        } finally {
          setAnalyzingLandId(null);
        }
      }, 3000);
    } catch (err) {
      if (err.response?.status === 429) {
        setAiError("AI Quota Finished. Please try again later.");
      } else {
        setAiError("Failed to trigger AI Analysis.");
      }
      setAnalyzingLandId(null);
    }
  }, [preferredLandId]);

  return {
    lands,
    ndviData,
    cropHealth,
    harvest,
    backendOk,
    loading,
    aiInsights,
    aiLoading,
    aiError,
    analyzingLandId,
    preferredLandId,
    stats,
    triggerAnalysis,
    refetch: load,
  };
}