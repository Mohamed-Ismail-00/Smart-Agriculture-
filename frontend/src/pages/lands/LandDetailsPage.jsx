/**
 * pages/lands/LandDetailsPage.jsx
 * Slim orchestrator for single-land intelligence view.
 */

import React, { useState, useEffect, useMemo } from "react";
import { useParams } from "react-router-dom";
import { useLandDetail } from "../../hooks/useLandDetail";
import { useBreakpoint } from "../../hooks/useBreakpoint";
import LandDetailHeader from "../../features/land-detail/LandDetailHeader";
import LandDetailMobileNav from "../../features/land-detail/LandDetailMobileNav";
import LandAiInsightsSection from "../../features/land-detail/LandAiInsightsSection";
import LandMetricsSection from "../../features/land-detail/LandMetricsSection";
import LandSatelliteSection from "../../features/land-detail/LandSatelliteSection";
import LandCropsSection from "../../features/land-detail/LandCropsSection";
import LandEnvironmentSection from "../../features/land-detail/LandEnvironmentSection";
import LandWaterSection from "../../features/land-detail/LandWaterSection";
import LandTimeRangeFilter from "../../features/land-detail/LandTimeRangeFilter";
import "../Lands.css";

export default function LandDetailsPage() {
  const { id } = useParams();
  const { isDrawer } = useBreakpoint();
  const isMobileLayout = isDrawer;
  const [activeMobileSection, setActiveMobileSection] = useState("overview");

  const {
    land,
    crops,
    soil,
    climate,
    water,
    images,
    cropHealth,
    harvest,
    cropZones,
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
    setSelectedZoneId,
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
    layers,
    derived,
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
  } = useLandDetail(id);

  const {
    cropsByType,
    primaryZone,
    visibleClimate,
    visibleWater,
    avgClimateTemp,
    avgWaterEt0,
    filteredClimate,
    filteredWater,
    filteredCrops,
    timeRangeCounts,
    timeRangeMetricBreakdown,
    timeRangeSummaryText,
    hasSyntheticCrops,
    satelliteDateRange,
  } = derived;

  const availableSections = useMemo(() => {
    const sections = ["overview", "crops", "satellite"];
    if (trackedVars.includes("soil") || trackedVars.includes("climate")) {
      sections.push("environment");
    }
    if (trackedVars.includes("water")) {
      sections.push("water");
    }
    return sections;
  }, [trackedVars]);

  useEffect(() => {
    if (!availableSections.includes(activeMobileSection)) {
      setActiveMobileSection("overview");
    }
  }, [availableSections, activeMobileSection]);

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

  const overviewSection = (
    <>
      <LandMetricsSection
        trackedVars={trackedVars}
        derived={derived}
        harvest={harvest}
        land={land}
        harvestTick={harvestTick}
        declaredCrop={cropDetection?.declared_crop}
      />
      <LandAiInsightsSection
        landId={id}
        aiInsights={aiInsights}
        aiLoading={aiLoading}
        aiError={aiError}
        analyzingLandId={analyzingLandId}
        onTriggerAnalysis={handleTriggerAnalysis}
      />
    </>
  );

  const cropsSection = (
    <LandCropsSection
      crops={filteredCrops}
      cropsByType={cropsByType}
      cropZones={cropZones}
      primaryZone={primaryZone}
      selectedZoneId={selectedZoneId}
      onZoneChange={setSelectedZoneId}
      hasSyntheticCrops={hasSyntheticCrops}
      cropHealth={cropHealth}
      harvest={harvest}
      land={land}
      trackedVars={trackedVars}
      handleReanalyze={handleReanalyze}
      reanalyzing={reanalyzing}
      timeRangeSummaryText={timeRangeSummaryText}
      timeRangeDays={timeRangeDays}
      cropDetection={cropDetection}
      trustSummary={trustSummary}
      cropConfirmOpen={cropConfirmOpen}
      setCropConfirmOpen={setCropConfirmOpen}
      declaringCrop={declaringCrop}
      onDeclareCrop={handleDeclareCrop}
    />
  );

  const satelliteSection = (
    <LandSatelliteSection
      land={land}
      images={images}
      layers={layers}
      activeLayer={activeLayer}
      setActiveLayer={setActiveLayer}
      derived={derived}
      showAllImages={showAllImages}
      setShowAllImages={setShowAllImages}
    />
  );

  const environmentSection = (
    <LandEnvironmentSection
      trackedVars={trackedVars}
      climate={filteredClimate}
      soilProfile={soilProfile}
      onRetrySoilProfile={handleRetrySoilProfile}
      soilRetryLoading={soilRetryLoading}
      climateSampling={climateSampling}
      areaHectares={areaHectares}
      visibleClimate={visibleClimate}
      avgClimateTemp={avgClimateTemp}
      showAllClimate={showAllClimate}
      setShowAllClimate={setShowAllClimate}
      timeRangeSummaryText={timeRangeSummaryText}
    />
  );

  const waterSection = trackedVars.includes("water") ? (
    <LandWaterSection
      water={filteredWater}
      visibleWater={visibleWater}
      land={land}
      avgWaterEt0={avgWaterEt0}
      showAllWater={showAllWater}
      setShowAllWater={setShowAllWater}
      timeRangeSummaryText={timeRangeSummaryText}
    />
  ) : null;

  const mobilePanels = {
    overview: overviewSection,
    crops: cropsSection,
    satellite: satelliteSection,
    environment: environmentSection,
    water: waterSection,
  };

  return (
    <React.Fragment>
      <div className={`anim-fade-in land-detail${isMobileLayout ? " land-detail--mobile" : ""}`}>
        <LandDetailHeader
          land={land}
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
          isMobile={isMobileLayout}
        />

        <LandTimeRangeFilter
          value={timeRangeDays}
          onChange={setTimeRangeDays}
          counts={timeRangeCounts}
          metricBreakdown={timeRangeMetricBreakdown}
          summaryText={timeRangeSummaryText}
        />

        {isMobileLayout ? (
          <>
            <LandDetailMobileNav
              activeSection={activeMobileSection}
              onSectionChange={setActiveMobileSection}
              availableSections={availableSections}
            />
            <div className="land-detail__panel" key={activeMobileSection}>
              {mobilePanels[activeMobileSection]}
            </div>
          </>
        ) : (
          <>
            {overviewSection}
            {cropsSection}
            {satelliteSection}
            {environmentSection}
            {waterSection}
          </>
        )}
      </div>
    </React.Fragment>
  );
}