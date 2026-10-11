/**
 * components/map/MapDrawComponent.jsx
 * Interactive Leaflet map: find a place (governorate, search, my location),
 * then mark the field. One click drops a box on the field and its corners are
 * dragged into place; drawing corner by corner is the alternative.
 */

import { useEffect, useRef, useState, useCallback } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet-draw";
import "leaflet-draw/dist/leaflet.draw.css";
import { useBreakpoint } from "../../hooks/useBreakpoint";
import "./Map.css";

import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
});

const EGYPT_CENTER = [26.8, 30.8];
const EGYPT_ZOOM = 7;

const TILE_LAYERS = {
  satellite: {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attribution: "&copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics",
  },
  street: {
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution: "&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a>",
  },
};

// Bounding boxes [south, north, west, east] from OpenStreetMap (Nominatim).
const DELTA_GOVERNORATES = [
  { key: "sharqia", en: "Sharqia", ar: "الشرقية", box: [30.198, 31.062, 31.279, 32.226] },
  { key: "kafr-el-sheikh", en: "Kafr El-Sheikh", ar: "كفر الشيخ", box: [30.963, 31.8, 30.209, 31.412] },
  { key: "dakahlia", en: "Dakahlia", ar: "الدقهلية", box: [30.558, 31.728, 31.2, 32.346] },
  { key: "gharbia", en: "Gharbia", ar: "الغربية", box: [30.575, 31.104, 30.747, 31.301] },
  { key: "monufia", en: "Monufia", ar: "المنوفية", box: [30.171, 30.702, 30.354, 31.258] },
  { key: "beheira", en: "Beheira", ar: "البحيرة", box: [29.92, 31.663, 29.617, 30.851] },
  { key: "qalyubia", en: "Qalyubia", ar: "القليوبية", box: [30.093, 30.575, 31.055, 31.63] },
  { key: "damietta", en: "Damietta", ar: "دمياط", box: [31.105, 31.735, 31.491, 32.065] },
];

const HECTARES_PER_FEDDAN = 0.420083;
// Below this zoom a single field is too small on screen to mark.
const MIN_MARK_ZOOM = 14;
// Half the side of the starting box, as a share of the map's shorter side.
const START_BOX_SHARE = 0.12;
const ARABIC_CHARS = /[؀-ۿ]/;
const COORDINATES = /^\s*(-?\d+(?:\.\d+)?)\s*[,\s]\s*(-?\d+(?:\.\d+)?)\s*$/;

function boxToBounds([south, north, west, east]) {
  return [[south, west], [north, east]];
}

async function searchPlaces(query) {
  const params = new URLSearchParams({
    format: "jsonv2",
    q: query,
    countrycodes: "eg",
    limit: "5",
    "accept-language": ARABIC_CHARS.test(query) ? "ar" : "en",
  });
  const res = await fetch(`https://nominatim.openstreetmap.org/search?${params}`);
  if (!res.ok) throw new Error("search failed");
  return res.json();
}

const DRAW_SHAPE_OPTS = {
  color: "#22c55e",
  fillColor: "#22c55e",
  fillOpacity: 0.15,
  weight: 2.5,
  dashArray: "6, 4",
};

function computeAreaHectares(latLngs) {
  if (!latLngs || latLngs.length < 3) return 0;
  if (L.GeometryUtil && L.GeometryUtil.geodesicArea) {
    return L.GeometryUtil.geodesicArea(latLngs) / 10000;
  }
  let area = 0;
  for (let i = 0; i < latLngs.length; i++) {
    const j = (i + 1) % latLngs.length;
    area += latLngs[i].lng * latLngs[j].lat;
    area -= latLngs[j].lng * latLngs[i].lat;
  }
  area = Math.abs(area) / 2;
  const m2 = area * 111320 * 111320 * Math.cos((latLngs[0].lat * Math.PI) / 180);
  return m2 / 10000;
}

function polygonToGeoJSON(latLngs) {
  const coords = latLngs.map((ll) => [ll.lng, ll.lat]);
  if (
    coords.length > 0 &&
    (coords[0][0] !== coords[coords.length - 1][0] ||
      coords[0][1] !== coords[coords.length - 1][1])
  ) {
    coords.push([...coords[0]]);
  }
  return { type: "Polygon", coordinates: [coords] };
}

function extractFromLayer(layer) {
  const latLngs = layer.getLatLngs()[0];
  const center = layer.getBounds().getCenter();
  const hectares = computeAreaHectares(latLngs);
  return {
    geojson: polygonToGeoJSON(latLngs),
    stats: {
      center: [center.lat, center.lng],
      areaApprox: Math.round(hectares * 100) / 100,
      areaFeddan: Math.round((hectares / HECTARES_PER_FEDDAN) * 100) / 100,
      vertexCount: latLngs.length,
    },
  };
}

function FullscreenIcon({ exit }) {
  if (exit) {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <polyline points="4 14 10 14 10 20" />
        <polyline points="20 10 14 10 14 4" />
        <line x1="14" y1="10" x2="21" y2="3" />
        <line x1="3" y1="21" x2="10" y2="14" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="15 3 21 3 21 9" />
      <polyline points="9 21 3 21 3 15" />
      <line x1="21" y1="3" x2="14" y2="10" />
      <line x1="3" y1="21" x2="10" y2="14" />
    </svg>
  );
}

export default function MapDrawComponent({ onGeometryChange, onFullscreenChange }) {
  const { isMobile, isDrawer } = useBreakpoint();
  const isCompactUI = isDrawer;

  const mapElRef = useRef(null);
  const mapObjRef = useRef(null);
  const drawnItemsRef = useRef(null);
  const tileRef = useRef(null);
  const callbackRef = useRef(onGeometryChange);
  const activeDrawRef = useRef(null);
  const placingRef = useRef(false);

  const [activeLayer, setActiveLayer] = useState("satellite");
  const [hasShape, setHasShape] = useState(false);
  const [shapeStats, setShapeStats] = useState(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [drawHint, setDrawHint] = useState(null);
  const [activeTool, setActiveTool] = useState(null);
  const [vertexCount, setVertexCount] = useState(0);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [locatorMessage, setLocatorMessage] = useState(null);

  useEffect(() => {
    callbackRef.current = onGeometryChange;
  }, [onGeometryChange]);

  const emitGeometry = useCallback((geojson, stats) => {
    setHasShape(!!geojson);
    setShapeStats(geojson ? stats : null);
    if (callbackRef.current) callbackRef.current(geojson, stats);
  }, []);

  const stopActiveDraw = useCallback(() => {
    if (activeDrawRef.current) {
      try {
        activeDrawRef.current.disable();
      } catch {
        // already disabled
      }
      activeDrawRef.current = null;
    }
    placingRef.current = false;
    setActiveTool(null);
    setVertexCount(0);
    setDrawHint(null);
    const map = mapObjRef.current;
    if (map) {
      map.dragging.enable();
      map.getContainer().style.cursor = "";
    }
  }, []);

  const commitLayer = useCallback((layer) => {
    if (!drawnItemsRef.current) return false;
    const { geojson, stats } = extractFromLayer(layer);

    if (stats.areaApprox < 0.001) {
      setDrawHint("Shape too small — zoom in and draw a larger area.");
      emitGeometry(null, null);
      return false;
    }

    drawnItemsRef.current.clearLayers();
    drawnItemsRef.current.addLayer(layer);
    emitGeometry(geojson, stats);
    setDrawHint(null);

    // Corners stay draggable: the numbers follow the drag, the form is told when it ends.
    layer.editing?.enable();
    layer.on("editdrag", () => setShapeStats(extractFromLayer(layer).stats));
    layer.on("edit", () => {
      const edited = extractFromLayer(layer);
      emitGeometry(edited.geojson, edited.stats);
    });
    requestAnimationFrame(() => {
      mapObjRef.current?.invalidateSize({ animate: false });
    });
    return true;
  }, [emitGeometry]);

  useEffect(() => {
    if (mapObjRef.current) return;

    const map = L.map(mapElRef.current, {
      center: EGYPT_CENTER,
      zoom: EGYPT_ZOOM,
      zoomControl: false,
      maxZoom: 19,
    });

    L.control.zoom({ position: "bottomleft" }).addTo(map);

    const tile = L.tileLayer(TILE_LAYERS.satellite.url, {
      attribution: TILE_LAYERS.satellite.attribution,
      maxZoom: 19,
    }).addTo(map);
    tileRef.current = tile;

    const drawnItems = new L.FeatureGroup();
    map.addLayer(drawnItems);
    drawnItemsRef.current = drawnItems;

    map.on(L.Draw.Event.CREATED, (e) => {
      stopActiveDraw();
      commitLayer(e.layer);
    });

    map.on(L.Draw.Event.DRAWVERTEX, (e) => {
      setVertexCount(e.layers.getLayers().length);
    });

    map.on("click", (e) => {
      if (!placingRef.current) return;
      if (map.getZoom() < MIN_MARK_ZOOM) {
        setDrawHint("Zoom in until you can see your field, then click on it");
        return;
      }
      const size = map.getSize();
      const half = Math.min(size.x, size.y) * START_BOX_SHARE;
      const point = map.latLngToContainerPoint(e.latlng);
      const corners = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([dx, dy]) =>
        map.containerPointToLatLng([point.x + dx * half, point.y + dy * half])
      );
      stopActiveDraw();
      commitLayer(L.polygon(corners, DRAW_SHAPE_OPTS));
    });

    mapObjRef.current = map;
    setTimeout(() => map.invalidateSize(), 200);

    return () => {
      stopActiveDraw();
      map.remove();
      mapObjRef.current = null;
    };
  }, [commitLayer, stopActiveDraw]);

  useEffect(() => {
    if (!mapObjRef.current) return;
    const map = mapObjRef.current;
    const refresh = () => map.invalidateSize({ animate: false });
    const t1 = setTimeout(refresh, isFullscreen ? 80 : 30);
    const t2 = setTimeout(refresh, isFullscreen ? 240 : 120);
    const t3 = setTimeout(refresh, isFullscreen ? 480 : 0);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, [isFullscreen, isCompactUI]);

  useEffect(() => {
    if (isFullscreen) {
      document.body.classList.add("map-draw-body-lock");
    } else {
      document.body.classList.remove("map-draw-body-lock");
    }

    const handleKey = (e) => {
      if (e.key === "Escape") {
        stopActiveDraw();
        setIsFullscreen(false);
      }
    };
    if (isFullscreen) document.addEventListener("keydown", handleKey);

    const timer = setTimeout(() => mapObjRef.current?.invalidateSize({ animate: false }), 200);

    return () => {
      clearTimeout(timer);
      document.removeEventListener("keydown", handleKey);
    };
  }, [isFullscreen, stopActiveDraw]);

  useEffect(() => () => {
    document.body.classList.remove("map-draw-body-lock");
  }, []);

  useEffect(() => {
    onFullscreenChange?.(isFullscreen);
  }, [isFullscreen, onFullscreenChange]);

  const switchLayer = useCallback((layerKey) => {
    if (!tileRef.current) return;
    setActiveLayer(layerKey);
    tileRef.current.setUrl(TILE_LAYERS[layerKey].url);
  }, []);

  const clearShape = useCallback(() => {
    stopActiveDraw();
    drawnItemsRef.current?.clearLayers();
    emitGeometry(null, null);
  }, [emitGeometry, stopActiveDraw]);

  const startDraw = useCallback((tool) => {
    const map = mapObjRef.current;
    if (!map) return;

    stopActiveDraw();

    if (tool === "place") {
      placingRef.current = true;
      map.getContainer().style.cursor = "crosshair";
      setActiveTool(tool);
      setDrawHint(isMobile ? "Tap the middle of your field" : "Click the middle of your field");
      return;
    }

    let handler = null;
    let hint = "";

    if (tool === "polygon") {
      handler = new L.Draw.Polygon(map, {
        allowIntersection: false,
        // leaflet-draw 1.0.4 throws in its area tooltip (undeclared variable in
        // readableArea) once a polygon has three points, which blocks a fourth.
        showArea: false,
        shapeOptions: DRAW_SHAPE_OPTS,
      });
      hint = isMobile
        ? "Tap each corner of the field, then press Finish"
        : "Click each corner of the field, then press Finish";
    }

    if (!handler) return;
    handler.enable();
    activeDrawRef.current = handler;
    setActiveTool(tool);
    setDrawHint(hint);
  }, [isMobile, stopActiveDraw]);

  const undoLastPoint = useCallback(() => {
    const handler = activeDrawRef.current;
    if (!handler?.deleteLastVertex) return;
    handler.deleteLastVertex();
    setVertexCount((count) => Math.max(0, count - 1));
  }, []);

  const finishPolygon = useCallback(() => {
    activeDrawRef.current?.completeShape?.();
  }, []);

  const goToGovernorate = useCallback((governorate) => {
    setResults(null);
    setLocatorMessage(null);
    mapObjRef.current?.flyToBounds(boxToBounds(governorate.box), { duration: 1.2 });
  }, []);

  const goToResult = useCallback((place) => {
    setResults(null);
    setQuery(place.display_name);
    mapObjRef.current?.flyToBounds(boxToBounds(place.boundingbox.map(Number)), { duration: 1.2, maxZoom: 16 });
  }, []);

  const runSearch = useCallback(async () => {
    const text = query.trim();
    if (!text) return;
    setLocatorMessage(null);

    const coords = text.match(COORDINATES);
    if (coords) {
      setResults(null);
      mapObjRef.current?.flyTo([Number(coords[1]), Number(coords[2])], 16, { duration: 1.2 });
      return;
    }

    setSearching(true);
    try {
      const places = await searchPlaces(text);
      if (places.length === 0) {
        setResults(null);
        setLocatorMessage("No place found. Try the name of the village, town or district.");
      } else if (places.length === 1) {
        goToResult(places[0]);
      } else {
        setResults(places);
      }
    } catch {
      setResults(null);
      setLocatorMessage("Search is not available right now. Pick a governorate or move the map.");
    } finally {
      setSearching(false);
    }
  }, [goToResult, query]);

  const goToMyLocation = useCallback(() => {
    setResults(null);
    if (!navigator.geolocation) {
      setLocatorMessage("This browser cannot share your location.");
      return;
    }
    setLocatorMessage("Finding your location…");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocatorMessage(null);
        mapObjRef.current?.flyTo([position.coords.latitude, position.coords.longitude], 16, { duration: 1.2 });
      },
      () => setLocatorMessage("Could not get your location. Allow location access, or use the search."),
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }, []);

  const enterFullscreen = useCallback((e) => {
    e?.preventDefault?.();
    e?.stopPropagation?.();
    setIsFullscreen(true);
  }, []);

  const exitFullscreen = useCallback((e) => {
    e?.preventDefault?.();
    e?.stopPropagation?.();
    stopActiveDraw();
    setIsFullscreen(false);
  }, [stopActiveDraw]);

  const toggleFullscreen = useCallback((e) => {
    if (isFullscreen) exitFullscreen(e);
    else enterFullscreen(e);
  }, [enterFullscreen, exitFullscreen, isFullscreen]);

  const wrapperClass = [
    "map-draw-wrapper",
    isCompactUI ? "map-draw-wrapper--compact" : "",
    isFullscreen ? "map-draw-wrapper--fullscreen" : "",
  ].filter(Boolean).join(" ");

  const drawTools = [
    { key: "place", label: "Mark my field", icon: "◎" },
    { key: "polygon", label: "Draw corners", icon: "⬠" },
  ];

  const locatorBar = (
    <div className="map-locator">
      <div className="map-locator__search" role="search">
        <input
          type="search"
          className="map-locator__input"
          placeholder="Search a village or town — ابحث باسم القرية أو المدينة"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              runSearch();
            }
          }}
          dir="auto"
          aria-label="Search for a place"
        />
        <button
          type="button"
          className="map-locator__btn map-locator__btn--primary"
          onClick={runSearch}
          disabled={searching || !query.trim()}
        >
          {searching ? "Searching…" : "Search"}
        </button>
        <button type="button" className="map-locator__btn" onClick={goToMyLocation}>
          My location
        </button>
        {results && (
          <ul className="map-locator__results">
            {results.map((place) => (
              <li key={place.place_id}>
                <button type="button" dir="auto" onClick={() => goToResult(place)}>
                  {place.display_name}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="map-locator__chips" aria-label="Delta governorates">
        {DELTA_GOVERNORATES.map((governorate) => (
          <button
            key={governorate.key}
            type="button"
            className="map-locator__chip"
            onClick={() => goToGovernorate(governorate)}
          >
            {governorate.en} <span lang="ar">{governorate.ar}</span>
          </button>
        ))}
      </div>
      {locatorMessage && <div className="map-locator__message" role="status">{locatorMessage}</div>}
    </div>
  );

  const desktopControls = !isCompactUI && !isFullscreen && (
    <div className="map-top-controls map-top-controls--desktop">
      <div className="map-toolbar">
        <button
          type="button"
          className={`map-toolbar__btn${activeLayer === "satellite" ? " map-toolbar__btn--active" : ""}`}
          onClick={() => switchLayer("satellite")}
        >
          Satellite
        </button>
        <button
          type="button"
          className={`map-toolbar__btn${activeLayer === "street" ? " map-toolbar__btn--active" : ""}`}
          onClick={() => switchLayer("street")}
        >
          Street
        </button>
      </div>
      <div className="map-toolbar">
        {drawTools.map((tool) => (
          <button
            key={tool.key}
            type="button"
            className={`map-toolbar__btn map-toolbar__btn--draw${tool.key === "place" ? " map-toolbar__btn--main" : ""}${activeTool === tool.key ? " map-toolbar__btn--active" : ""}`}
            onClick={() => startDraw(tool.key)}
          >
            <span aria-hidden="true">{tool.icon}</span> {tool.label}
          </button>
        ))}
      </div>
      <button
        type="button"
        className="map-toolbar__btn map-fullscreen-btn"
        onClick={toggleFullscreen}
        aria-label="Enter fullscreen"
      >
        <FullscreenIcon exit={false} />
      </button>
    </div>
  );

  const drawActions = activeTool && (
    <div className="map-draw-actions" role="status">
      <span className="map-draw-actions__hint">{drawHint}</span>
      {activeTool === "polygon" && (
        <>
          <button type="button" className="btn btn--secondary btn--sm" onClick={undoLastPoint} disabled={vertexCount === 0}>
            Undo point
          </button>
          <button type="button" className="btn btn--primary btn--sm" onClick={finishPolygon} disabled={vertexCount < 3}>
            Finish
          </button>
        </>
      )}
      <button type="button" className="btn btn--ghost btn--sm" onClick={stopActiveDraw}>
        Cancel
      </button>
    </div>
  );

  const mapUI = (
    <div className={wrapperClass}>
      {isFullscreen && (
        <div className="map-fullscreen-chrome">
          <div className="map-fullscreen-topbar">
            <button
              type="button"
              className="map-fullscreen-topbar__back"
              onClick={exitFullscreen}
              onPointerDown={(e) => e.stopPropagation()}
              aria-label="Exit fullscreen map"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M19 12H5M12 19l-7-7 7-7" />
              </svg>
              Back
            </button>
            <span className="map-fullscreen-topbar__title">Draw boundary</span>
            {isCompactUI ? (
              <button
                type="button"
                className="map-fullscreen-topbar__close"
                onClick={exitFullscreen}
                onPointerDown={(e) => e.stopPropagation()}
                aria-label="Close fullscreen map"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            ) : (
              <button
                type="button"
                className="map-fullscreen-topbar__done"
                onClick={exitFullscreen}
                onPointerDown={(e) => e.stopPropagation()}
              >
                Done
              </button>
            )}
          </div>
          {isCompactUI ? (
            <div className="map-fullscreen-topbar__layers">
              <button
                type="button"
                className={`map-mobile-pill${activeLayer === "satellite" ? " map-mobile-pill--active" : ""}`}
                onClick={() => switchLayer("satellite")}
                onPointerDown={(e) => e.stopPropagation()}
              >
                Satellite
              </button>
              <button
                type="button"
                className={`map-mobile-pill${activeLayer === "street" ? " map-mobile-pill--active" : ""}`}
                onClick={() => switchLayer("street")}
                onPointerDown={(e) => e.stopPropagation()}
              >
                Street
              </button>
            </div>
          ) : (
            <div className="map-fullscreen-toolbar">
              <div className="map-toolbar">
                <button
                  type="button"
                  className={`map-toolbar__btn${activeLayer === "satellite" ? " map-toolbar__btn--active" : ""}`}
                  onClick={() => switchLayer("satellite")}
                >
                  Satellite
                </button>
                <button
                  type="button"
                  className={`map-toolbar__btn${activeLayer === "street" ? " map-toolbar__btn--active" : ""}`}
                  onClick={() => switchLayer("street")}
                >
                  Street
                </button>
              </div>
              <div className="map-toolbar map-fullscreen-toolbar__draw">
                {drawTools.map((tool) => (
                  <button
                    key={tool.key}
                    type="button"
                    className={`map-toolbar__btn map-toolbar__btn--draw${tool.key === "place" ? " map-toolbar__btn--main" : ""}${activeTool === tool.key ? " map-toolbar__btn--active" : ""}`}
                    onClick={() => startDraw(tool.key)}
                  >
                    <span aria-hidden="true">{tool.icon}</span> {tool.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
      {locatorBar}

      {/* Mobile compact header */}
      {isCompactUI && !isFullscreen && (
        <div className="map-mobile-header">
          <div className="map-mobile-header__layers">
            <button
              type="button"
              className={`map-mobile-pill${activeLayer === "satellite" ? " map-mobile-pill--active" : ""}`}
              onClick={() => switchLayer("satellite")}
            >
              Satellite
            </button>
            <button
              type="button"
              className={`map-mobile-pill${activeLayer === "street" ? " map-mobile-pill--active" : ""}`}
              onClick={() => switchLayer("street")}
            >
              Street
            </button>
          </div>
          <button
            type="button"
            className="map-mobile-expand-btn"
            onClick={enterFullscreen}
            onPointerDown={(e) => e.stopPropagation()}
            aria-label="Expand map to fullscreen"
          >
            <FullscreenIcon exit={false} />
            <span>Expand</span>
          </button>
        </div>
      )}

      <div className="map-draw-canvas">
        <div ref={mapElRef} className="map-container" />
        {desktopControls}
        {drawActions}

        {!hasShape && !activeTool && (
          <div className="map-instructions">
            <svg className="map-instructions__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M3 6l9-4 9 4" />
              <path d="M3 6v12l9 4 9-4V6" />
            </svg>
            <div className="map-instructions__text">
              {drawHint || "Find your field, then mark it"}
            </div>
            {!drawHint && (
              <div className="map-instructions__sub">
                Pick a governorate or search above, zoom in, press Mark my field and click on it
              </div>
            )}
          </div>
        )}

        {hasShape && shapeStats && (
          <div className="map-info-panel">
            <div className="map-info-panel__stats">
              <div className="map-info-panel__stat">
                <span className="map-info-panel__stat-value">{shapeStats.areaApprox} ha</span>
                <span className="map-info-panel__stat-label">Area</span>
              </div>
              <div className="map-info-panel__stat">
                <span className="map-info-panel__stat-value">{shapeStats.areaFeddan}</span>
                <span className="map-info-panel__stat-label">Feddan</span>
              </div>
            </div>
            <div className="map-info-panel__tip">
              Drag the white corners to fit your field. Drag a faint point on an edge to add a corner.
            </div>
            <div className="map-info-panel__actions">
              <button type="button" className="btn btn--ghost btn--sm" onClick={clearShape}>
                Clear
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Mobile bottom draw dock */}
      {isCompactUI && (
        <div className={`map-draw-dock${isFullscreen ? " map-draw-dock--fullscreen" : ""}`}>
          {drawTools.map((tool) => (
            <button
              key={tool.key}
              type="button"
              className={`map-draw-dock__btn${activeTool === tool.key ? " map-draw-dock__btn--active" : ""}`}
              onClick={() => startDraw(tool.key)}
            >
              <span className="map-draw-dock__icon" aria-hidden="true">{tool.icon}</span>
              <span className="map-draw-dock__label">{tool.label}</span>
            </button>
          ))}
        </div>
      )}

    </div>
  );

  return mapUI;
}