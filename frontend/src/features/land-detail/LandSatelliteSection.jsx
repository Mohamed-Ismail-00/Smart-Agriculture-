/**
 * LandSatelliteSection — field boundary on the map + Sentinel-2 images of the season
 */

import MapViewComponent from "../../components/map/MapViewComponent";
import { formatDate } from "./landDetailUtils";

export default function LandSatelliteSection({
  land,
  layers,
  activeLayer,
  setActiveLayer,
  seasonImages,
  visibleImages,
  showAllImages,
  setShowAllImages,
}) {
  return (
    <section className="land-detail__section">
      <div className="section-header">
        <h2 className="section-header__title">Satellite view</h2>
        <span className="badge badge--neutral">{seasonImages.length} images this season</span>
      </div>

      <MapViewComponent
        latitude={land.latitude}
        longitude={land.longitude}
        boundaryPolygon={land.boundary_polygon}
        areaHectares={land.area_hectares}
        name={land.name}
      />

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
        </div>
        <div style={{ padding: "var(--space-md)" }}>
          {seasonImages.length === 0 ? (
            <div className="empty-state" style={{ padding: "var(--space-xl)" }}>
              <p className="text-body-sm">No {activeLayer === "ndvi" ? "NDVI" : "true color"} images in this season.</p>
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
                        <span>{img.image_type === "ndvi" ? "NDVI" : "True Color"}</span>
                      )}
                    </div>
                    <div className="text-caption">{formatDate(img.date)}</div>
                    {img.ndvi_mean != null && (
                      <span className="badge badge--healthy">NDVI {Number(img.ndvi_mean).toFixed(2)}</span>
                    )}
                  </div>
                ))}
              </div>
              {seasonImages.length > 6 && (
                <div style={{ marginTop: "var(--space-md)", textAlign: "center" }}>
                  <button className="btn btn--ghost" onClick={() => setShowAllImages(!showAllImages)}>
                    {showAllImages ? "Show less" : `Show all (${seasonImages.length})`}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
