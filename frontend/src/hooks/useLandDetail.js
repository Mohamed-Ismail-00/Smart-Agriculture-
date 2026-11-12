/**
 * hooks/useLandDetail.js — Land detail data + actions (web + RN ready)
 */

import { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  getLandDetail,
  getLandTimeseries,
  getLandImages,
  getCropDetection,
  declarePrimaryCrop,
  getSoilProfile,
  retrySoilProfile,
  reanalyzeLand,
  updateLandSettings,
  deleteLand,
  exportLand,
  resolveLandImageGallery,
  revokeBlobImageUrls,
} from "../services/api";
import { useConfirm } from "../context/ConfirmContext";
import { useNotifications } from "../context/NotificationContext";
import {
  defaultSeasonKey,
  filterBySeason,
  listSeasons,
  summarizeWeather,
} from "../features/land-detail/landDetailUtils";

const LAYERS = [
  { key: "true_color", label: "True Color" },
  { key: "ndvi", label: "NDVI" },
];

const READY = ["active", "ready", "active_partial", "completed"];

export function useLandDetail(landId) {
  const navigate = useNavigate();
  const confirm = useConfirm();
  const { addNotification } = useNotifications();

  const [land, setLand] = useState(null);
  const [climate, setClimate] = useState([]);
  const [crops, setCrops] = useState([]);
  const [water, setWater] = useState([]);
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeLayer, setActiveLayer] = useState("true_color");
  const [reanalyzing, setReanalyzing] = useState(false);
  const [showProgressModal, setShowProgressModal] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [intervalDays, setIntervalDays] = useState(16);
  const [showAllImages, setShowAllImages] = useState(false);
  const [seasonKey, setSeasonKey] = useState(null);
  const [soilProfile, setSoilProfile] = useState(null);
  const [soilRetryLoading, setSoilRetryLoading] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [cropDetection, setCropDetection] = useState(null);
  const [cropConfirmOpen, setCropConfirmOpen] = useState(false);
  const [declaringCrop, setDeclaringCrop] = useState(false);

  const areaHectares = land?.area_hectares != null ? Number(land.area_hectares) : null;

  const fetchAll = useCallback(async () => {
    if (!landId) return;
    setLoading(true);
    setError(null);
    try {
      const [landRes, climateRes, cropsRes, waterRes, imagesRes, soilProfileRes, detectionRes] =
        await Promise.all([
          getLandDetail(landId),
          getLandTimeseries(landId, "climate").catch(() => ({ points: [] })),
          getLandTimeseries(landId, "crops").catch(() => ({ points: [] })),
          getLandTimeseries(landId, "water").catch(() => ({ points: [] })),
          getLandImages(landId).catch(() => ({ images: [] })),
          getSoilProfile(landId).catch(() => null),
          getCropDetection(landId).catch(() => null),
        ]);

      setLand(landRes);
      setClimate(climateRes.points || []);
      setCrops(cropsRes.points || []);
      setWater(waterRes.points || []);
      const galleryImages = await resolveLandImageGallery(imagesRes.images || []);
      setImages((prev) => {
        revokeBlobImageUrls(prev);
        return galleryImages;
      });
      setSoilProfile(soilProfileRes);
      setCropDetection(detectionRes);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [landId]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  useEffect(() => () => revokeBlobImageUrls(images), [images]);

  useEffect(() => {
    setSeasonKey(null);
  }, [landId]);

  useEffect(() => {
    let interval;
    if (land && !READY.includes(land.status)) {
      setReanalyzing(true);
      interval = setInterval(async () => {
        try {
          const updatedLand = await getLandDetail(landId);
          setLand(updatedLand);
          if (READY.includes(updatedLand.status)) {
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
    setShowAllImages(false);
  }, [seasonKey]);

  const seasons = useMemo(() => listSeasons(crops), [crops]);
  const season = seasons.find((s) => s.key === seasonKey) || seasons.find((s) => s.key === defaultSeasonKey(seasons));

  const handleRetrySoilProfile = useCallback(async () => {
    if (!landId) return;
    setSoilRetryLoading(true);
    try {
      const profile = await retrySoilProfile(landId);
      setSoilProfile(profile);
      if (!profile?.profile_available) {
        throw new Error(profile?.last_fetch_error || "Soil profile still unavailable");
      }
      addNotification({ type: "success", message: "Soil profile fetched successfully" });
    } finally {
      setSoilRetryLoading(false);
    }
  }, [landId, addNotification]);

  const handleDeclareCrop = useCallback(async ({ crop_type, notes }) => {
    if (!landId) return;
    setDeclaringCrop(true);
    try {
      await declarePrimaryCrop(landId, { crop_type, notes });
      setCropDetection(await getCropDetection(landId));
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

  const derived = useMemo(() => {
    const seasonCrops = filterBySeason(crops, season);
    const seasonClimate = filterBySeason(climate, season);
    const seasonWater = filterBySeason(water, season);
    const seasonImages = filterBySeason(images, season, "date").filter((img) =>
      activeLayer === "true_color" ? img.image_type === "true_color" : img.image_type === "ndvi"
    );
    const lastOf = (items, field = "timestamp") =>
      items.length ? items.reduce((max, i) => (i[field] > max ? i[field] : max), items[0][field]) : null;

    return {
      seasonCrops,
      seasonClimate,
      seasonImages,
      visibleImages: showAllImages ? seasonImages : seasonImages.slice(0, 6),
      weather: summarizeWeather(seasonClimate, seasonWater, areaHectares),
      seasonWater,
      lastSatellite: lastOf(crops),
      lastWeather: lastOf(climate),
      hasSyntheticCrops: seasonCrops.some((c) => c.payload?.data_source === "synthetic"),
    };
  }, [crops, climate, water, images, season, activeLayer, showAllImages, areaHectares]);

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
    images,
    loading,
    error,
    activeLayer,
    setActiveLayer,
    reanalyzing,
    showProgressModal,
    setShowProgressModal,
    showSettings,
    setShowSettings,
    intervalDays,
    setIntervalDays,
    showAllImages,
    setShowAllImages,
    seasons,
    season,
    setSeasonKey,
    soilProfile,
    soilRetryLoading,
    handleRetrySoilProfile,
    areaHectares,
    isExporting,
    layers: LAYERS,
    derived,
    fetchAll,
    handleExport,
    handleReanalyze,
    handleDelete,
    handleSaveSettings,
    navigate,
    cropDetection,
    cropConfirmOpen,
    setCropConfirmOpen,
    declaringCrop,
    handleDeclareCrop,
  };
}
