/**
 * components/map/MapViewComponent.jsx
 * ------------------------------------
 * Read-only Leaflet map that displays a land boundary polygon
 * on top of satellite imagery tiles.
 *
 * Props:
 *   latitude       — center lat
 *   longitude      — center lng
 *   boundaryPolygon — GeoJSON { type: "Polygon", coordinates: [...] } or null
 *   areaHectares   — number (displayed in info)
 *   name           — land name (shown in popup)
 *
 * Follows: documents/Frontend/07_UI_UX_Style_Guide.md
 * Plan:    documents/Frontend/08_Map_and_Satellite_Integration_Plan.md §2
 */

import { useEffect, useRef, useState, useCallback } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./Map.css";

/* ── Fix marker icons ─────────────────────────────────────────── */
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
});

/* ── Tile layers ──────────────────────────────────────────────── */
const TILES = {
  satellite: {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr: "&copy; Esri",
  },
  street: {
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attr: "&copy; OpenStreetMap",
  },
  topo: {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
    attr: "&copy; Esri",
  },
};

/* ── Boundary styling (design-system green) ───────────────────── */
const BOUNDARY_STYLE = {
  color: "#22c55e",       // green-500
  fillColor: "#22c55e",
  fillOpacity: 0.12,
  weight: 2.5,
};

const BOUNDARY_HOVER_STYLE = {
  color: "#16a34a",       // green-600
  fillOpacity: 0.22,
  weight: 3,
};

/* ═══════════════════════════════════════════════════════════════ */
/*  MapViewComponent                                              */
/* ═══════════════════════════════════════════════════════════════ */

export default function MapViewComponent({
  latitude,
  longitude,
  boundaryPolygon,
  areaHectares,
  name,
}) {
  const mapElRef = useRef(null);
  const mapObjRef = useRef(null);
  const tileRef = useRef(null);
  const wrapperRef = useRef(null);

  const [activeLayer, setActiveLayer] = useState("satellite");
  const [isFullscreen, setIsFullscreen] = useState(false);

  /* ── Initialize map ─────────────────────────────────────────── */
  useEffect(() => {
    if (mapObjRef.current) return;

    const center = [latitude || 26.8, longitude || 30.8];
    const zoom = boundaryPolygon ? 14 : 7;

    const map = L.map(mapElRef.current, {
      center,
      zoom,
      zoomControl: false,
      scrollWheelZoom: true,
    });

    L.control.zoom({ position: "topright" }).addTo(map);

    // Tile layer
    const tile = L.tileLayer(TILES.satellite.url, {
      attribution: TILES.satellite.attr,
      maxZoom: 19,
    }).addTo(map);
    tileRef.current = tile;

    // Add boundary polygon
    if (boundaryPolygon && boundaryPolygon.coordinates) {
      // GeoJSON coordinates are [lng, lat], Leaflet needs [lat, lng]
      const coords = boundaryPolygon.coordinates[0].map(([lng, lat]) => [lat, lng]);

      const polygon = L.polygon(coords, BOUNDARY_STYLE).addTo(map);

      // Hover effect
      polygon.on("mouseover", () => polygon.setStyle(BOUNDARY_HOVER_STYLE));
      polygon.on("mouseout", () => polygon.setStyle(BOUNDARY_STYLE));

      // Popup
      polygon.bindPopup(
        `<div style="font-family: Inter, sans-serif; text-align: center;">
          <strong style="font-size: 14px;">${name || "Land"}</strong><br/>
          <span style="color: #6b7280; font-size: 12px;">
            ${areaHectares ? `${areaHectares} hectares` : ""}
          </span>
        </div>`,
        { className: "map-popup" }
      );

      // Fit map to polygon bounds with padding
      map.fitBounds(polygon.getBounds(), { padding: [50, 50], maxZoom: 16 });
    } else {
      // No polygon — just place a marker at centroid
      L.marker(center)
        .addTo(map)
        .bindPopup(
          `<strong>${name || "Land"}</strong><br/>${areaHectares ? areaHectares + " ha" : ""}`
        );
    }

    mapObjRef.current = map;

    // Fix tiles on first render
    setTimeout(() => map.invalidateSize(), 200);

    return () => {
      map.remove();
      mapObjRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ── Invalidate on fullscreen toggle ────────────────────────── */
  useEffect(() => {
    if (mapObjRef.current) {
      const timer = setTimeout(() => {
        mapObjRef.current.invalidateSize({ animate: true });
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [isFullscreen]);

  /* ── Switch tile layer ─────────────────────────────────────── */
  const switchLayer = useCallback((key) => {
    if (!mapObjRef.current || !tileRef.current) return;
    setActiveLayer(key);
    tileRef.current.setUrl(TILES[key].url);
  }, []);

  /* ── Fullscreen toggle ──────────────────────────────────────── */
  const toggleFullscreen = useCallback(() => {
    setIsFullscreen((prev) => !prev);
  }, []);

  /* ── ESC exits fullscreen ───────────────────────────────────── */
  useEffect(() => {
    if (!isFullscreen) return;
    const handleKey = (e) => {
      if (e.key === "Escape") setIsFullscreen(false);
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [isFullscreen]);

  return (
    <div
      ref={wrapperRef}
      className={`map-view-wrapper${isFullscreen ? " map-view-wrapper--fullscreen" : ""}`}
    >
      {/* Top controls */}
      <div className="map-top-controls">
        <div className="map-toolbar">
          {Object.entries({
            satellite: "🛰️ Satellite",
            street: "🗺️ Street",
            topo: "🏔️ Topo",
          }).map(([key, label]) => (
            <button
              key={key}
              type="button"
              className={`map-toolbar__btn${activeLayer === key ? " map-toolbar__btn--active" : ""}`}
              onClick={() => switchLayer(key)}
            >
              {label}
            </button>
          ))}
        </div>
        <button
          type="button"
          className="map-toolbar__btn map-fullscreen-btn"
          onClick={toggleFullscreen}
          title={isFullscreen ? "Exit fullscreen (Esc)" : "Fullscreen"}
        >
          {isFullscreen ? (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 16, height: 16 }}>
              <polyline points="4 14 10 14 10 20" />
              <polyline points="20 10 14 10 14 4" />
              <line x1="14" y1="10" x2="21" y2="3" />
              <line x1="3" y1="21" x2="10" y2="14" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 16, height: 16 }}>
              <polyline points="15 3 21 3 21 9" />
              <polyline points="9 21 3 21 3 15" />
              <line x1="21" y1="3" x2="14" y2="10" />
              <line x1="3" y1="21" x2="10" y2="14" />
            </svg>
          )}
        </button>
      </div>

      {/* Map */}
      <div ref={mapElRef} className="map-container map-container--view" />

      {/* Bottom info bar */}
      {boundaryPolygon && (
        <div className="map-view-info">
          <span className="map-view-info__item">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14 }}>
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" />
              <circle cx="12" cy="10" r="3" />
            </svg>
            {latitude?.toFixed(4)}°N, {longitude?.toFixed(4)}°E
          </span>
          <span className="map-view-info__item">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14 }}>
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <path d="M3 9h18M9 3v18" />
            </svg>
            {areaHectares || "—"} ha
          </span>
          <span className="map-view-info__badge">
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#22c55e", display: "inline-block" }} />
            Land Boundary
          </span>
        </div>
      )}
    </div>
  );
}
