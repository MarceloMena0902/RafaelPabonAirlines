/**
 * FlightMap.jsx  —  Mapa 2D infinito (react-leaflet)
 * ──────────────────────────────────────────────────────────────
 * Gran círculo para cada arco → sin corte en el antimeridiano.
 * El mapa se puede desplazar horizontalmente de forma infinita.
 */
import { useEffect, useState, useRef, useMemo, useCallback } from "react";
import { MapContainer, TileLayer, Polyline, CircleMarker, Marker, Tooltip, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useTranslation } from "react-i18next";
import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const WINE = "#8B1B3D";
const GOLD = "#D4A017";

// Coordenadas de los 15 aeropuertos
const AIRPORT_COORDS = {
  ATL: { lat: 33.6407, lon:  -84.4277, name: "Atlanta" },
  PEK: { lat: 40.0801, lon:  116.5846, name: "Pekín" },
  DXB: { lat: 25.2532, lon:   55.3657, name: "Dubai" },
  TYO: { lat: 35.5494, lon:  139.7798, name: "Tokio" },
  LON: { lat: 51.4775, lon:   -0.4614, name: "Londres" },
  LAX: { lat: 33.9425, lon: -118.4081, name: "Los Ángeles" },
  PAR: { lat: 49.0097, lon:    2.5479, name: "París" },
  FRA: { lat: 50.0379, lon:    8.5622, name: "Fráncfort" },
  IST: { lat: 41.2608, lon:   28.7418, name: "Estambul" },
  SIN: { lat:  1.3644, lon:  103.9915, name: "Singapur" },
  MAD: { lat: 40.4983, lon:   -3.5676, name: "Madrid" },
  AMS: { lat: 52.3086, lon:    4.7639, name: "Ámsterdam" },
  DFW: { lat: 32.8998, lon:  -97.0403, name: "Dallas" },
  CAN: { lat: 23.3959, lon:  113.3080, name: "Cantón" },
  SAO: { lat:-23.4356, lon:  -46.4731, name: "São Paulo" },
};

// ── Gran círculo con longitudes normalizadas (evita corte antimeridiano) ──
function greatCirclePoints(lat1, lon1, lat2, lon2, n = 80) {
  const toRad = d => d * Math.PI / 180;
  const toDeg = r => r * 180 / Math.PI;
  const φ1 = toRad(lat1), λ1 = toRad(lon1);
  const φ2 = toRad(lat2), λ2 = toRad(lon2);
  const d = 2 * Math.asin(Math.sqrt(
    Math.sin((φ2 - φ1) / 2) ** 2 + Math.cos(φ1) * Math.cos(φ2) * Math.sin((λ2 - λ1) / 2) ** 2
  ));
  if (d < 0.001) return [[lat1, lon1], [lat2, lon2]];

  const pts = [];
  for (let i = 0; i <= n; i++) {
    const f = i / n;
    const A = Math.sin((1 - f) * d) / Math.sin(d);
    const B = Math.sin(f * d) / Math.sin(d);
    const x = A * Math.cos(φ1) * Math.cos(λ1) + B * Math.cos(φ2) * Math.cos(λ2);
    const y = A * Math.cos(φ1) * Math.sin(λ1) + B * Math.cos(φ2) * Math.sin(λ2);
    const z = A * Math.sin(φ1)              + B * Math.sin(φ2);
    pts.push([
      toDeg(Math.atan2(z, Math.sqrt(x ** 2 + y ** 2))),
      toDeg(Math.atan2(y, x)),
    ]);
  }

  // Normalizar longitudes: cada punto a ±180 del anterior → el arco es continuo
  for (let i = 1; i < pts.length; i++) {
    while (pts[i][1] - pts[i - 1][1] >  180) pts[i][1] -= 360;
    while (pts[i - 1][1] - pts[i][1] >  180) pts[i][1] += 360;
  }
  return pts;
}

// ── Ícono de avión con rotación ──────────────────────────────
function planeIcon(heading, color, size) {
  return L.divIcon({
    html: `<div style="font-size:${size}px;color:${color};transform:rotate(${heading ?? 0}deg);line-height:1;filter:drop-shadow(0 0 3px rgba(0,0,0,.7))">✈</div>`,
    iconSize:   [size, size],
    iconAnchor: [size / 2, size / 2],
    className:  "",
  });
}

// ── Volar a una posición al seleccionar vuelo ────────────────
function MapController({ target }) {
  const map = useMap();
  useEffect(() => {
    if (target) map.flyTo([target.lat, target.lon], Math.max(map.getZoom(), 4), { duration: 0.8 });
  }, [target]);
  return null;
}

// ── Componente contador en header ────────────────────────────
function LiveCounter({ lastUpdate, refreshing }) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center gap-2 text-xs text-gray-400">
      {refreshing
        ? <span className="animate-pulse text-yellow-400">{t("flightmap.update")}...</span>
        : lastUpdate && <span>{t("flightmap.last_update")} {lastUpdate.toLocaleTimeString()}</span>
      }
    </div>
  );
}

// ────────────────────────────────────────────────────────────
export default function FlightMap() {
  const { t }                       = useTranslation();
  const [flights, setFlights]       = useState([]);
  const [selected, setSelected]     = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError]           = useState(null);

  // Fetch vuelos en vivo
  const fetchLive = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    try {
      const res = await axios.get(`${API_BASE}/flights/live`);
      setFlights(res.data);
      setLastUpdate(new Date());
    } catch {
      setError(t("flightmap.server_error"));
    } finally {
      setRefreshing(false);
    }
  }, [t]);

  useEffect(() => {
    fetchLive();
    const timer = setInterval(fetchLive, 30000);
    return () => clearInterval(timer);
  }, [fetchLive]);

  // Aeropuertos activos
  const activeAirports = useMemo(
    () => new Set(flights.flatMap(f => [f.origin, f.destination])),
    [flights]
  );

  // Arcos con coordenadas de gran círculo (antimeridiano OK)
  const arcs = useMemo(() =>
    flights
      .filter(f => AIRPORT_COORDS[f.origin] && AIRPORT_COORDS[f.destination])
      .map(f => {
        const o = AIRPORT_COORDS[f.origin];
        const d = AIRPORT_COORDS[f.destination];
        return {
          ...f,
          positions: greatCirclePoints(o.lat, o.lon, d.lat, d.lon),
          isSelected: selected?.id === f.id,
        };
      }),
    [flights, selected]
  );

  return (
    <div className="flex flex-col flex-1 min-h-0" style={{ background: "#050a18" }}>

      {/* ── Header ───────────────────────────────────────────── */}
      <div
        className="flex items-center justify-between px-6 py-3 border-b shrink-0"
        style={{ background: "#0A1F44", borderColor: "#1e2a3a" }}
      >
        <div className="flex items-center gap-3">
          <span className="text-2xl">✈</span>
          <div>
            <h1 className="text-white font-bold text-lg tracking-wide">
              {t("flightmap.title")}
            </h1>
            <p className="text-blue-300 text-xs">
              {flights.length} {t("flightmap.active")}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <LiveCounter lastUpdate={lastUpdate} refreshing={refreshing} />
          <button
            onClick={fetchLive}
            disabled={refreshing}
            className="px-3 py-1.5 rounded-lg text-xs font-medium text-white transition-colors"
            style={{ background: refreshing ? "#333" : WINE }}
          >
            ↻ {t("flightmap.update")}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-900/80 text-red-200 text-sm px-6 py-2 text-center shrink-0">
          {error}
        </div>
      )}

      {/* ── Mapa + Panel lateral ─────────────────────────────── */}
      <div className="flex flex-1 min-h-0 overflow-hidden">

        {/* Mapa Leaflet */}
        <div className="flex-1 relative overflow-hidden">
          <MapContainer
            center={[20, 20]}
            zoom={2}
            minZoom={1}
            maxZoom={8}
            zoomControl={true}
            style={{ height: "100%", width: "100%", background: "#050a18" }}
          >
            <MapController target={selected} />

            {/* Capa base oscura — no requiere API key */}
            <TileLayer
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>'
              subdomains="abcd"
              maxZoom={20}
              noWrap={false}
            />

            {/* Arcos — gran círculo normalizado */}
            {arcs.map(arc => (
              <Polyline
                key={arc.id}
                positions={arc.positions}
                pathOptions={{
                  color:   arc.isSelected ? GOLD : (arc.is_demo ? GOLD : WINE),
                  weight:  arc.isSelected ? 2.5 : 1.4,
                  opacity: arc.isSelected ? 1 : 0.75,
                  dashArray: arc.is_demo ? "6 4" : null,
                }}
                eventHandlers={{
                  click: () => setSelected(selected?.id === arc.id ? null : arc),
                }}
              >
                <Tooltip sticky>
                  <span className="text-xs">
                    <b>{arc.origin} → {arc.destination}</b><br />
                    #{arc.id} · {Math.round(arc.fraction * 100)}%
                    {arc.is_demo ? " · DEMO" : ""}
                  </span>
                </Tooltip>
              </Polyline>
            ))}

            {/* Aeropuertos */}
            {Object.entries(AIRPORT_COORDS).map(([code, { lat, lon, name }]) => (
              <CircleMarker
                key={code}
                center={[lat, lon]}
                radius={activeAirports.has(code) ? 5 : 3}
                pathOptions={{
                  color:     activeAirports.has(code) ? GOLD : "#444",
                  fillColor: activeAirports.has(code) ? GOLD : "#555",
                  fillOpacity: 1,
                  weight: 0,
                }}
              >
                <Tooltip>
                  <span className="text-xs font-bold">{code}</span>
                  <span className="text-xs text-gray-500 ml-1">{name}</span>
                </Tooltip>
              </CircleMarker>
            ))}

            {/* Aviones en posición actual */}
            {flights.map(f => {
              if (f.lat == null || f.lon == null) return null;
              const isSel = selected?.id === f.id;
              const color = isSel ? GOLD : (f.is_demo ? GOLD : WINE);
              const size  = isSel ? 22 : 15;
              return (
                <Marker
                  key={`plane-${f.id}`}
                  position={[f.lat, f.lon]}
                  icon={planeIcon(f.heading, color, size)}
                  zIndexOffset={isSel ? 1000 : 0}
                  eventHandlers={{
                    click: () => setSelected(selected?.id === f.id ? null : f),
                  }}
                >
                  <Tooltip>
                    <span className="text-xs">
                      <b>{f.origin} → {f.destination}</b><br />
                      #{f.id} · {Math.round(f.fraction * 100)}%
                    </span>
                  </Tooltip>
                </Marker>
              );
            })}
          </MapContainer>

          {/* Sin vuelos */}
          {!refreshing && flights.length === 0 && !error && (
            <div
              className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2
                         rounded-2xl p-6 text-center z-[1000] pointer-events-none"
              style={{ background: "rgba(10,31,68,0.92)", border: "1px solid #1e3a5f" }}
            >
              <div className="text-4xl mb-2">🛫</div>
              <p className="text-white font-semibold">{t("flightmap.no_flights")}</p>
              <p className="text-gray-400 text-sm mt-1">{t("flightmap.no_flights_sub")}</p>
            </div>
          )}

          {/* Leyenda */}
          <div
            className="absolute bottom-8 left-4 rounded-xl p-3 text-xs z-[1000] space-y-1.5 pointer-events-none"
            style={{ background: "rgba(10,31,68,0.90)", border: "1px solid #1e3a5f" }}
          >
            <div className="text-gray-300 font-semibold mb-1">{t("flightmap.legend")}</div>
            <div className="flex items-center gap-2 text-gray-300">
              <span style={{ color: WINE, fontSize: 14 }}>✈</span>
              <span>{t("flightmap.active_flight")}</span>
            </div>
            <div className="flex items-center gap-2 text-gray-300">
              <span style={{ color: GOLD, fontSize: 14 }}>✈</span>
              <span>{t("flightmap.demo_flight")}</span>
            </div>
            <div className="flex items-center gap-2 text-gray-300">
              <span className="inline-block w-3 h-3 rounded-full" style={{ background: GOLD }} />
              <span>{t("flightmap.active_airport")}</span>
            </div>
          </div>
        </div>

        {/* ── Panel lateral ────────────────────────────────── */}
        <div
          className="w-72 flex flex-col overflow-y-auto shrink-0"
          style={{ background: "#0d1117", borderLeft: "1px solid #1e2a3a" }}
        >
          <div className="px-4 py-3 border-b shrink-0" style={{ borderColor: "#1e2a3a" }}>
            <p className="text-white font-semibold text-sm">{t("flightmap.sidebar_title")}</p>
          </div>

          {flights.length === 0 && !refreshing && (
            <div className="flex-1 flex items-center justify-center text-gray-600 text-sm px-4 text-center">
              {t("flightmap.no_flights")}
            </div>
          )}

          {flights.map(flight => {
            const isSelected = selected?.id === flight.id;
            const isDemo     = !!flight.is_demo;
            const pct        = Math.round(flight.fraction * 100);

            return (
              <button
                key={flight.id}
                onClick={() => setSelected(isSelected ? null : flight)}
                className="w-full text-left px-4 py-3 border-b transition-colors shrink-0"
                style={{
                  borderColor: "#1e2a3a",
                  background: isSelected ? "rgba(139,27,61,0.2)" : "transparent",
                }}
              >
                {/* Ruta */}
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-bold text-base" style={{ color: isDemo ? GOLD : WINE }}>
                    {flight.origin}
                  </span>
                  <span className="text-gray-500 text-xs">→</span>
                  <span className="font-bold text-base" style={{ color: isDemo ? GOLD : WINE }}>
                    {flight.destination}
                  </span>
                  {isDemo && (
                    <span className="ml-auto text-xs px-1.5 py-0.5 rounded font-bold"
                      style={{ background: GOLD, color: "#0A1F44" }}>
                      DEMO
                    </span>
                  )}
                </div>

                <div className="text-xs text-gray-400 space-y-0.5">
                  <div>{t("flightmap.flight")} #{flight.id} · {flight.aircraft_type || "—"}</div>
                  <div>{t("flightmap.departure")}: {flight.departure_time} UTC · {flight.duration_hours}h</div>
                </div>

                {/* Barra de progreso */}
                <div className="mt-2">
                  <div className="flex justify-between text-xs text-gray-500 mb-1">
                    <span>{AIRPORT_COORDS[flight.origin]?.name || flight.origin}</span>
                    <span>{pct}%</span>
                    <span>{AIRPORT_COORDS[flight.destination]?.name || flight.destination}</span>
                  </div>
                  <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "#1e2a3a" }}>
                    <div
                      className="h-full rounded-full transition-all"
                      style={{ width: `${pct}%`, background: isSelected ? GOLD : WINE }}
                    />
                  </div>
                </div>

                {/* Detalle expandido */}
                {isSelected && (
                  <div className="mt-3 space-y-1 text-xs border-t pt-2" style={{ borderColor: "#1e2a3a" }}>
                    <div className="flex justify-between">
                      <span className="text-gray-400">{t("flightmap.lat_lon")}</span>
                      <span className="text-white font-mono">
                        {flight.lat?.toFixed(2)}, {flight.lon?.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">{t("flightmap.heading")}</span>
                      <span className="text-white">{flight.heading}°</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">{t("flightmap.node")}</span>
                      <span className="text-white capitalize">{flight.node_owner}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">{t("flightmap.remaining")}</span>
                      <span className="text-white">
                        {Math.round(flight.duration_hours * (1 - flight.fraction) * 60)} min
                      </span>
                    </div>
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
