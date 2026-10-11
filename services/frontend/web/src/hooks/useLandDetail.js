/**
 * hooks/useLandDetail.js — Land detail data + actions (web + RN ready)
 */

import { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  getLandDetail,
  getLandTimeseries,
  getLandImages,
  getCropHealth,
  getHarvestPrediction,
  getCropZones,
  getCropDetection,
  getTrustSummary,
  declarePrimaryCrop,
  getSoilProfile,
  retrySoilProfile,
  reanalyzeLand,
  updateLandSettings,
  getAiInsights,
  triggerAiAnalysis,
  triggerAiAnalysisAsync,
  deleteLand,
  exportLand,
  resolveLandImageGallery,
  revokeBlobImageUrls,
} from "../services/api";
import { useConfirm } from "../context/ConfirmContext";
import { useNotifications } from "../context/NotificationContext";
import {
  filterImagesByTimeRange,
  filterPointsByTimeRange,
  formatTimeRangeSummary,
  getPrimaryZone,
  getMultiMetricTimeRangeCounts,
  getTimeRangeSummary,
  groupCropsByType,
} from "../features/land-detail/landDetailUtils";

const LAYERS = [
  { key: "true_color", label: "True Color" },
  { key: "ndvi", label: "NDVI" },
];

export function useLandDetail(landId) {
  const navigate = useNavigate();
  const confirm = useConfirm();
  const { addNotification } = useNotifications();

  const [land, setLand] = useState(null);
  const [climate, setClimate] = useState([]);
  const [crops, setCrops] = useState([]);
  const [soil, setSoil] = useState([]);
  const [water, setWater] = useState([]);
  const [images, setImages] = useState([]);
  const [cropHealth, setCropHealth] = useState(null);
  const [harvest, setHarvest] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeLayer, setActiveLayer] = useState("true_color");
  const [cropZones, setCropZones] = useState([]);
  const [reanalyzing, setReanalyzing] = useState(false);
  const [showProgressModal, setShowProgressModal] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [intervalDays, setIntervalDays] = useState(16);
  const [showAllClimate, setShowAllClimate] = useState(false);
  const [showAllWater, setShowAllWater] = useState(false);
  const [showAllImages, setShowAllImages] = useState(false);
  const [timeRangeDays, setTimeRangeDays] = useState(30);
  const [harvestTick, setHarvestTick] = useState(0);
  const [selectedZoneId, setSelectedZoneId] = useState(null);
  const [soilProfile, setSoilProfile] = useState(null);
  const [soilRetryLoading, setSoilRetryLoading] = useState(false);
  const [aiInsights, setAiInsights] = useState([]);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState(null);
  const [analyzingLandId, setAnalyzingLandId] = useState(null);
  const [isExporting, setIsExporting] = useState(false);
  const [cropDetection, setCropDetection] = useState(null);
  const [trustSummary, setTrustSummary] = useState(null);
  const [cropConfirmOpen, setCropConfirmOpen] = useState(false);
  const [declaringCrop, setDeclaringCrop] = useState(false);

  const trackedVars = land?.metadata_?.trackingVariables || ["ndvi", "climate", "soil", "water"];
  const climateSampling = land?.metadata_?.climate_sampling || climate[0]?.payload?.spatial_sample || null;
  const areaHectares = land?.area_hectares != null ? Number(land.area_hectares) : null;

  const refreshHarvest = useCallback(async () => {
    if (!landId) return;
    try {
      const harvestRes = await getHarvestPrediction(landId);
      setHarvest(harvestRes);
    } catch {
      // non-fatal — keep last known prediction
    }
  }, [landId]);

  const fetchAll = useCallback(async () => {
    if (!landId) return;
    setLoading(true);
    setError(null);
    try {
      const [
        landRes, climateRes, cropsRes, soilRes,
        waterRes, imagesRes, zonesRes, healthRes,
        harvestRes, soilProfileRes, detectionRes, trustRes,
      ] = await Promise.all([
        getLandDetail(landId),
        getLandTimeseries(landId, "climate").catch(() => ({ points: [] })),
        getLandTimeseries(landId, "crops").catch(() => ({ points: [] })),
        getLandTimeseries(landId, "soil").catch(() => ({ points: [] })),
        getLandTimeseries(landId, "water").catch(() => ({ points: [] })),
        getLandImages(landId).catch(() => ({ images: [] })),
        getCropZones(landId).catch(() => ({ zones: [] })),
        getCropHealth(landId).catch(() => null),
        getHarvestPrediction(landId).catch(() => null),
        getSoilProfile(landId).catch(() => null),
        getCropDetection(landId).catch(() => null),
        getTrustSummary(landId).catch(() => null),
      ]);

      setLand(landRes);
      setClimate(climateRes.points || []);
      setCrops(cropsRes.points || []);
      setSoil(soilRes.points || []);
      setWater(waterRes.points || []);
      const galleryImages = await resolveLandImageGallery(imagesRes.images || []);
      setImages((prev) => {
        revokeBlobImageUrls(prev);
        return galleryImages;
      });
      setCropZones(zonesRes.zones || []);
      setCropHealth(healthRes);
      setHarvest(harvestRes);
      setSoilProfile(soilProfileRes);
      setCropDetection(detectionRes);
      setTrustSummary(trustRes);
      const primary = getPrimaryZone(zonesRes.zones || []);
      if (primary?.zone_id != null) {
        setSelectedZoneId(primary.zone_id);
      }

      setAiLoading(true);
      setAiError(null);
      getAiInsights(landId)
        .then((r) => {
          const insights = r.insights || [];
          setAiInsights(insights);
          insights.forEach((insight) => {
            const data = insight.structured_data || {};
            const isRealAlert =
              (data.risk_flags && data.risk_flags.length > 0) ||
              ["poor", "critical"].includes(data.ndvi_assessment || data.spectral_assessment || "");
            if (isRealAlert) {
              addNotification({
                type: "ai_alert",
                severity: "high",
                message: insight.title + ": " + (insight.body || "").slice(0, 80) + "...",
                land_id: landId,
              });
            }
          });
        })
        .catch((err) => {
          if (err.response?.status === 429) {
            setAiError("AI Quota Finished. Please try again later.");
          } else {
            setAiError("Could not load AI Insights right now.");
          }
        })
        .finally(() => setAiLoading(false));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [landId, addNotification]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  useEffect(() => () => revokeBlobImageUrls(images), [images]);

  useEffect(() => {
    setSelectedZoneId(null);
    setTimeRangeDays(30);
  }, [landId]);

  // Recompute days-to-harvest as calendar days pass (hourly tick)
  useEffect(() => {
    const tick = setInterval(() => setHarvestTick((n) => n + 1), 60 * 60 * 1000);
    return () => clearInterval(tick);
  }, []);

  // Refresh harvest prediction from API periodically and when tab refocuses
  useEffect(() => {
    if (!landId) return undefined;
    const poll = setInterval(refreshHarvest, 30 * 60 * 1000);
    const onVisible = () => {
      if (document.visibilityState === "visible") refreshHarvest();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearInterval(poll);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [landId, refreshHarvest]);

  useEffect(() => {
    let interval;
    if (land && !["active", "ready", "active_partial", "completed"].includes(land.status)) {
      setReanalyzing(true);
      interval = setInterval(async () => {
        try {
          const updatedLand = await getLandDetail(landId);
          setLand(updatedLand);
          if (["active", "ready", "active_partial", "completed"].includes(updatedLand.status)) {
            clearInterval(interval);
            fetchAll();
            setShowProgressModal(false);
          }
        } catch (e) {
          console.error("Polling error:", e);
        }
      }, 2000);
    } else {
      setReanalyzing(false);
      setShowProgressModal(false);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [land?.status, landId, fetchAll]);

  useEffect(() => {
    setShowAllClimate(false);
    setShowAllWater(false);
    setShowAllImages(false);
  }, [timeRangeDays]);

  const handleRetrySoilProfile = useCallback(async () => {
    if (!landId) return;
    setSoilRetryLoading(true);
    try {
      const profile = await retrySoilProfile(landId);
      setSoilProfile(profile);
      const trustRes = await getTrustSummary(landId).catch(() => null);
      if (trustRes) setTrustSummary(trustRes);
      if (!profile?.profile_available) {
        throw new Error(profile?.last_fetch_error || "Soil profile still unavailable");
      }
      addNotification({ type: "success", message: "Soil profile fetched successfully" });
    } finally {
      setSoilRetryLoading(false);
    }
  }, [landId]);

  const handleDeclareCrop = useCallback(async ({ crop_type, notes }) => {
    if (!landId) return;
    setDeclaringCrop(true);
    try {
      await declarePrimaryCrop(landId, { crop_type, notes });
      const [detectionRes, trustRes, zonesRes] = await Promise.all([
        getCropDetection(landId),
        getTrustSummary(landId),
        getCropZones(landId),
      ]);
      setCropDetection(detectionRes);
      setTrustSummary(trustRes);
      setCropZones(zonesRes?.zones || []);
      setCropConfirmOpen(false);
      addNotification({
        type: "success",
        message: `Crop confirmed: ${crop_type.split("(")[0].trim()}`,
      });
    } catch (err) {
      addNotification({
        type: "error",
        message: err?.response?.data?.detail || "Failed to confirm crop",
      });
    } finally {
      setDeclaringCrop(false);
    }
  }, [landId, addNotification]);

  const handleZoneChange = useCallback(async (zoneId) => {
    setSelectedZoneId(zoneId);
    if (!landId || zoneId == null) return;
    try {
      const res = await getLandTimeseries(landId, "crops", zoneId);
      setCrops(res.points || []);
    } catch {
      // keep existing series
    }
  }, [landId]);

  const derived = useMemo(() => {
    const filteredClimate = filterPointsByTimeRange(climate, timeRangeDays);
    const filteredWater = filterPointsByTimeRange(water, timeRangeDays);
    const filteredCrops = filterPointsByTimeRange(crops, timeRangeDays);
    const filteredImagesAll = filterImagesByTimeRange(images, timeRangeDays);

    const referencePoints = climate.length
      ? climate
      : water.length
        ? water
        : soil.length
          ? soil
          : crops.length
            ? crops
            : images;
    const { breakdown: timeRangeMetricBreakdown, pillCounts: timeRangeCounts } =
      getMultiMetricTimeRangeCounts({ climate, water, crops, images });
    const activeMetrics = timeRangeMetricBreakdown[timeRangeDays ?? "all"] || {
      climate: 0,
      water: 0,
      ndvi: 0,
      images: 0,
    };
    const timeRangeSummary = getTimeRangeSummary(referencePoints, timeRangeDays);
    const fc = activeMetrics.climate;
    const fw = activeMetrics.water;
    const fcr = activeMetrics.ndvi;
    const fi = activeMetrics.images;
    const baseSummary = formatTimeRangeSummary(timeRangeSummary);
    const timeRangeSummaryText = baseSummary.includes("No records")
      ? baseSummary
      : `${baseSummary} · ${fc} climate · ${fw} water · ${fcr} NDVI · ${fi} images`;

    const hasSyntheticCrops = filteredCrops.some(
      (c) => c.payload?.data_source === "synthetic",
    );
    const satelliteDateRange =
      filteredImagesAll.length > 0
        ? {
            start: filteredImagesAll[0].date || filteredImagesAll[0].timestamp,
            end: filteredImagesAll[filteredImagesAll.length - 1].date ||
              filteredImagesAll[filteredImagesAll.length - 1].timestamp,
          }
        : null;

    const latestCrop = filteredCrops.length > 0 ? filteredCrops[filteredCrops.length - 1] : null;
    const latestClimate = filteredClimate.length > 0 ? filteredClimate[filteredClimate.length - 1] : null;
    const latestWater = filteredWater.length > 0 ? filteredWater[filteredWater.length - 1] : null;
    const primaryZone = getPrimaryZone(cropZones);
    const primaryCropType = primaryZone
      ? primaryZone.crop_type
      : (filteredCrops.length > 0 ? filteredCrops[filteredCrops.length - 1].payload?.crop_type : null);
    const cropsByType = groupCropsByType(filteredCrops);
    const filteredImages = filteredImagesAll.filter((img) =>
      activeLayer === "true_color" ? img.image_type === "true_color" : img.image_type === "ndvi"
    );
    const visibleImages = showAllImages ? filteredImages : filteredImages.slice(0, 6);
    const reversedClimate = [...filteredClimate].reverse();
    const visibleClimate = showAllClimate ? reversedClimate : reversedClimate.slice(0, 6);
    const reversedWater = [...filteredWater].reverse();
    const visibleWater = showAllWater ? reversedWater : reversedWater.slice(0, 6);
    const avgClimateTemp = filteredClimate.length > 0
      ? (
          filteredClimate.reduce(
            (acc, c) => acc + (c.payload?.temperature_mean_c ?? c.value ?? 0),
            0,
          ) / filteredClimate.length
        ).toFixed(1)
      : "—";
    const avgWaterEt0 = filteredWater.length > 0
      ? (
          filteredWater.reduce((acc, w) => acc + (w.payload?.crop_water_requirement_mm || 0), 0) /
          filteredWater.length
        ).toFixed(1)
      : "—";

    return {
      latestCrop,
      latestClimate,
      latestWater,
      primaryZone,
      primaryCropType,
      cropsByType,
      filteredClimate,
      filteredWater,
      filteredCrops,
      filteredImages,
      visibleImages,
      visibleClimate,
      visibleWater,
      avgClimateTemp,
      avgWaterEt0,
      timeRangeCounts,
      timeRangeMetricBreakdown,
      timeRangeSummaryText,
      hasSyntheticCrops,
      satelliteDateRange,
    };
  }, [
    crops, climate, soil, water, cropZones, images, activeLayer, timeRangeDays,
    showAllImages, showAllClimate, showAllWater,
  ]);

  const handleExport = useCallback(async () => {
    try {
      setIsExporting(true);
      const blob = await exportLand(landId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `land_${landId}_export.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      addNotification({
        type: "system",
        severity: "high",
        message: `Export failed: ${err.message || "Could not generate Excel file."}`,
      });
    } finally {
      setIsExporting(false);
    }
  }, [landId, addNotification]);

  const handleReanalyze = useCallback(async (refreshSections = ["environment", "satellite", "crops"]) => {
    try {
      setReanalyzing(true);
      setShowProgressModal(true);
      await reanalyzeLand(landId, refreshSections);
      setLand((prev) => (prev ? { ...prev, status: "processing" } : prev));
    } catch (err) {
      setError("Re-analysis failed: " + err.message);
      setReanalyzing(false);
      setShowProgressModal(false);
    }
  }, [landId]);

  const handleTriggerAnalysis = useCallback(async () => {
    setAnalyzingLandId(landId);
    setAiError(null);
    try {
      await triggerAiAnalysisAsync(landId);
      addNotification({
        type: "ai_analysis_queued",
        severity: "low",
        message: "AI analysis started for this land. You'll be notified when complete. ✨",
        land_id: landId,
      });
      setTimeout(async () => {
        try {
          const res = await getAiInsights(landId);
          setAiInsights(res.insights || []);
          setAiError(null);
        } catch {
          // non-fatal
        } finally {
          setAnalyzingLandId(null);
        }
      }, 4000);
    } catch (err) {
      if (err.response?.status === 429) {
        setAiError("AI Quota Finished. Please try again later.");
      } else {
        try {
          await triggerAiAnalysis(landId);
          const res = await getAiInsights(landId);
          setAiInsights(res.insights || []);
          setAiError(null);
        } catch (fallbackErr) {
          setAiError(fallbackErr.response?.data?.detail || "Failed to trigger AI Analysis.");
        }
      }
      setAnalyzingLandId(null);
    }
  }, [landId, addNotification]);

  const handleDelete = useCallback(async () => {
    const confirmed = await confirm({
      title: "Delete Land",
      message: "Are you sure you want to delete this land? This action cannot be undone and will delete all associated data.",
      confirmLabel: "Delete",
      cancelLabel: "Cancel",
      variant: "danger",
    });
    if (!confirmed) return;
    try {
      await deleteLand(landId);
      navigate("/lands");
    } catch (err) {
      addNotification({
        type: "system",
        severity: "high",
        message: `Failed to delete land: ${err.message}`,
      });
    }
  }, [landId, confirm, navigate, addNotification]);

  const handleSaveSettings = useCallback(async () => {
    try {
      await updateLandSettings(landId, { monitoring_interval_days: parseInt(intervalDays) });
      setShowSettings(false);
    } catch (err) {
      addNotification({
        type: "system",
        severity: "high",
        message: `Failed to save settings: ${err.message}`,
      });
    }
  }, [landId, intervalDays, addNotification]);

  return {
    land,
    climate,
    crops,
    soil,
    water,
    images,
    cropHealth,
    harvest,
    loading,
    error,
    activeLayer,
    setActiveLayer,
    cropZones,
    reanalyzing,
    showProgressModal,
    setShowProgressModal,
    showSettings,
    setShowSettings,
    intervalDays,
    setIntervalDays,
    showAllClimate,
    setShowAllClimate,
    showAllWater,
    setShowAllWater,
    showAllImages,
    setShowAllImages,
    timeRangeDays,
    setTimeRangeDays,
    harvestTick,
    selectedZoneId,
    setSelectedZoneId: handleZoneChange,
    soilProfile,
    soilRetryLoading,
    handleRetrySoilProfile,
    climateSampling,
    areaHectares,
    aiInsights,
    aiLoading,
    aiError,
    analyzingLandId,
    isExporting,
    trackedVars,
    layers: LAYERS,
    derived,
    fetchAll,
    handleExport,
    handleReanalyze,
    handleTriggerAnalysis,
    handleDelete,
    handleSaveSettings,
    navigate,
    cropDetection,
    trustSummary,
    cropConfirmOpen,
    setCropConfirmOpen,
    declaringCrop,
    handleDeclareCrop,
  };
}