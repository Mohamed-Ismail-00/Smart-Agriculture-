/**
 * pages/lands/LandDetailsPage.jsx
 * One land, one growing season at a time: crop, growth curve, satellite images, weather and soil.
 */

import { useState } from "react";
import { useParams } from "react-router-dom";
import { useLandDetail } from "../../hooks/useLandDetail";
import { useBreakpoint } from "../../hooks/useBreakpoint";
import LandDetailHeader from "../../features/land-detail/LandDetailHeader";
import LandDetailMobileNav from "../../features/land-detail/LandDetailMobileNav";
import LandSeasonPicker from "../../features/land-detail/LandSeasonPicker";
import LandCropCard from "../../features/land-detail/LandCropCard";
import LandGrowthSection from "../../features/land-detail/LandGrowthSection";
import LandSatelliteSection from "../../features/land-detail/LandSatelliteSection";
import LandWeatherSection from "../../features/land-detail/LandWeatherSection";
import LandSoilCard from "../../features/land-detail/LandSoilCard";
import "../Lands.css";

const SOURCES =
  "Sources: Sentinel-2 L2A satellite images (ESA, via Microsoft Planetary Computer) · weather and ET₀ from Open-Meteo (estimates) · soil from ISRIC SoilGrids (estimate).";

export default function LandDetailsPage() {
  const { id } = useParams();
  const { isDrawer } = useBreakpoint();
  const [activeMobileSection, setActiveMobileSection] = useState("overview");

  const {
    land,
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
    isExporting,
    layers,
    derived,
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
  } = useLandDetail(id);

  if (loading) {
    return (
      <div className="anim-fade-in land-detail-loading">
        <div className="land-detail-loading__inner">
          <div className="spinner spinner--dark spinner--lg" />
          <p className="text-body-sm">Loading land data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-state anim-fade-in">
        <svg className="error-state__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="15" y1="9" x2="9" y2="15" />
          <line x1="9" y1="9" x2="15" y2="15" />
        </svg>
        <div className="error-state__message">{error}</div>
        <button className="btn btn--primary" onClick={() => navigate("/lands")}>
          Back to Lands
        </button>
      </div>
    );
  }

  if (!land) return null;

  const cropSection = (
    <>
      <LandCropCard
        cropDetection={cropDetection}
        cropConfirmOpen={cropConfirmOpen}
        setCropConfirmOpen={setCropConfirmOpen}
        declaringCrop={declaringCrop}
        onDeclareCrop={handleDeclareCrop}
      />
      <LandGrowthSection
        points={derived.seasonCrops}
        seasonLabel={season?.label}
        hasSynthetic={derived.hasSyntheticCrops}
        onReanalyze={handleReanalyze}
        reanalyzing={reanalyzing}
      />
    </>
  );

  const satelliteSection = (
    <LandSatelliteSection
      land={land}
      layers={layers}
      activeLayer={activeLayer}
      setActiveLayer={setActiveLayer}
      seasonImages={derived.seasonImages}
      visibleImages={derived.visibleImages}
      showAllImages={showAllImages}
      setShowAllImages={setShowAllImages}
    />
  );

  const environmentSection = (
    <>
      <LandWeatherSection
        climate={derived.seasonClimate}
        water={derived.seasonWater}
        summary={derived.weather}
        lastWeather={derived.lastWeather}
      />
      <LandSoilCard soilProfile={soilProfile} onRetry={handleRetrySoilProfile} retrying={soilRetryLoading} />
    </>
  );

  const mobilePanels = {
    overview: cropSection,
    satellite: satelliteSection,
    environment: environmentSection,
  };

  return (
    <div className={`anim-fade-in land-detail${isDrawer ? " land-detail--mobile" : ""}`}>
      <LandDetailHeader
        land={land}
        lastSatellite={derived.lastSatellite}
        reanalyzing={reanalyzing}
        isExporting={isExporting}
        showSettings={showSettings}
        setShowSettings={setShowSettings}
        showProgressModal={showProgressModal}
        setShowProgressModal={setShowProgressModal}
        intervalDays={intervalDays}
        setIntervalDays={setIntervalDays}
        onBack={() => navigate("/lands")}
        onDelete={handleDelete}
        onExport={handleExport}
        onReanalyze={handleReanalyze}
        onSaveSettings={handleSaveSettings}
        isMobile={isDrawer}
      />

      <LandSeasonPicker seasons={seasons} value={season} onChange={setSeasonKey} />

      {isDrawer ? (
        <>
          <LandDetailMobileNav activeSection={activeMobileSection} onSectionChange={setActiveMobileSection} />
          <div className="land-detail__panel" key={activeMobileSection}>
            {mobilePanels[activeMobileSection]}
          </div>
        </>
      ) : (
        <>
          {cropSection}
          {satelliteSection}
          {environmentSection}
        </>
      )}

      <p className="land-detail__sources text-caption">{SOURCES}</p>
    </div>
  );
}
