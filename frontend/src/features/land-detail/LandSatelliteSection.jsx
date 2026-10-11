/**
 * LandSatelliteSection — map view + satellite image gallery
 */

import MapViewComponent from "../../components/map/MapViewComponent";
import { LAND_DETAIL_SOURCES } from "./landDetailUtils";

function formatDateRange(start, end) {
  if (!start || !end) return null;
  const fmt = (d) =>
    new Date(d).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  return `${fmt(start)} – ${fmt(end)}`;
}

export default function LandSatelliteSection({
  land,
  images,
  layers,
  activeLayer,
  setActiveLayer,
  derived,
  showAllImages,
  setShowAllImages,
}) {
  const { filteredImages, visibleImages, satelliteDateRange } = derived;
  const dateRangeLabel = satelliteDateRange
    ? formatDateRange(satelliteDateRange.start, satelliteDateRange.end)
    : null;

  return (
    <div className="anim-stagger" style={{ "--stagger-index": 3 }}>
      <div className="section-header">
        <h2 className="section-header__title">Satellite View</h2>
        <span className="badge badge--neutral">{filteredImages.length} captures</span>
      </div>

      <MapViewComponent
        latitude={land.latitude}
        longitude={land.longitude}
        boundaryPolygon={land.boundary_polygon}
        areaHectares={land.area_hectares}
        name={land.name}
      />
      <p className="land-detail-section-footer text-caption" style={{ marginTop: "var(--space-xs)" }}>
        Map · registered land polygon · {LAND_DETAIL_SOURCES.satellite}
      </p>

      {images.length > 0 && (
        <div className="satellite-viewer" style={{ marginTop: "var(--space-md)" }}>
          <div className="satellite-viewer__controls">
            <div className="satellite-viewer__tabs">
              {layers.map((l) => (
                <button
                  key={l.key}
                  className={`satellite-viewer__tab${activeLayer === l.key ? " satellite-viewer__tab--active" : ""}`}
                  onClick={() => setActiveLayer(l.key)}
                >
                  {l.label}
                </button>
              ))}
            </div>
            <span className="text-caption">
              Sentinel-2
              {dateRangeLabel ? ` · ${dateRangeLabel}` : ""}
              {filteredImages.length > 0 ? ` · ${filteredImages.length} scenes` : ""}
            </span>
          </div>
          <div style={{ padding: "var(--space-md)" }}>
            {filteredImages.length === 0 ? (
              <div className="empty-state" style={{ padding: "var(--space-xl)" }}>
                <p className="text-body-sm">No {activeLayer.replace("_", " ")} images available.</p>
              </div>
            ) : (
              <>
                <div className="satellite-image-grid">
                  {visibleImages.map((img, i) => (
                    <div className="card satellite-image-card" key={img.id || i}>
                      <div className="satellite-image-card__thumb">
                        {img.image_url ? (
                          <img src={img.image_url} alt={`${img.image_type} — ${img.date}`} loading="lazy" />
                        ) : (
                          <span>{img.image_type === "ndvi" ? "🟢 NDVI" : "🛰️ True Color"}</span>
                        )}
                      </div>
                      <div className="text-caption">{new Date(img.date).toLocaleDateString()}</div>
                      {img.ndvi_mean != null && (
                        <span
                          className="badge badge--healthy"
                          title="NDVI mean from nearest crop observation or raster"
                        >
                          NDVI: {Number(img.ndvi_mean).toFixed(2)}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
                {filteredImages.length > 6 && (
                  <div style={{ marginTop: "var(--space-md)", textAlign: "center" }}>
                    <button className="btn btn--ghost" onClick={() => setShowAllImages(!showAllImages)}>
                      {showAllImages ? "Show Less" : `Show All (${filteredImages.length})`}
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
      {images.length === 0 && (
        <p className="land-detail-section-footer text-caption">
          {LAND_DETAIL_SOURCES.satellite}
        </p>
      )}
    </div>
  );
}