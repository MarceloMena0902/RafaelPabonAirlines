/**
 * FlightMap.jsx
 * ─────────────
 * Mapa de seguimiento de vuelos en tiempo real estilo FlightRadar24.
 * Usa react-leaflet con tiles de CartoDB Dark Matter.
 * Actualiza posiciones cada 30 segundos.
 */
import { useEffect, useState, useRef } from "react";
import { MapContainer, TileLayer, Marker, Tooltip, Polyline, useMap } from "react-leaflet";
import L from "leaflet";
import { useTranslation } from "react-i18next";
import axios from "axios";

// Fix: leaflet default icon paths broken with Vite
import markerIcon2x   from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon     from "leaflet/dist/images/marker-icon.png";
import markerShadow   from "leaflet/dist/images/marker-shadow.png";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl:       markerIcon,
  shadowUrl:     markerShadow,
});

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// Airport coords for drawing origin/destination markers
const AIRPORT_COORDS = {
  ATL: [33.6407,  -84.4277],
  PEK: [40.0801,  116.5846],
  DXB: [25.2532,   55.3657],
  TYO: [35.5494,  139.7798],
  LON: [51.4775,   -0.4614],
  LAX: [33.9425, -118.4081],
  PAR: [49.0097,    2.5479],
  FRA: [50.0379,    8.5622],
  IST: [41.2608,   28.7418],
  SIN: [ 1.3644,  103.9915],
  MAD: [40.4983,   -3.5676],
  AMS: [52.3086,    4.7639],
  DFW: [32.8998,  -97.0403],
  CAN: [23.3959,  113.3080],
  SAO: [-23.4356, -46.4731],
};

const AIRPORT_NAMES = {
  ATL: "Atlanta",
  PEK: "Pekín",
  DXB: "Dubai",
  TYO: "Tokio",
  LON: "Londres",
  LAX: "Los Ángeles",
  PAR: "París",
  FRA: "Fráncfort",
  IST: "Estambul",
  SIN: "Singapur",
  MAD: "Madrid",
  AMS: "Ámsterdam",
  DFW: "Dallas",
  CAN: "Cantón",
  SAO: "São Paulo",
};

// Wine color variants
const WINE   = "#8B1B3D";
const GOLD   = "#D4A017";
const NAVY   = "#0A1F44";

/** SVG airplane icon rotated to heading */
function makePlaneIcon(heading, isDemo = false) {
  const color = isDemo ? GOLD : WINE;
  const size  = isDemo ? 38 : 32;
  const svg = `
<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24"
     style="transform: rotate(${heading}deg); filter: drop-shadow(0 1px 3px rgba(0,0,0,0.6));">
  <path fill="${color}" d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"/>
</svg>`;
  return L.divIcon({
    html:        svg,
    className:   "",
    iconSize:    [size, size],
    iconAnchor:  [size / 2, size / 2],
    popupAnchor: [0, -size / 2],
  });
}

/** Small dot for airports */
function makeAirportIcon(active = false) {
  const color = active ? GOLD : "#555";
  const svg = `
<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14">
  <circle cx="7" cy="7" r="5" fill="${color}" stroke="white" stroke-width="1.5"/>
</svg>`;
  return L.divIcon({
    html:       svg,
    className:  "",
    iconSize:   [14, 14],
    iconAnchor: [7, 7],
  });
}

/** Compute great-circle path points for the polyline */
function gcPath(lat1, lon1, lat2, lon2, steps = 50) {
  const toRad = d => (d * Math.PI) / 180;
  const toDeg = r => (r * 180) / Math.PI;

  const phi1 = toRad(lat1), lam1 = toRad(lon1);
  const phi2 = toRad(lat2), lam2 = toRad(lon2);

  const d = Math.acos(
    Math.max(-1, Math.min(1,
      Math.sin(phi1) * Math.sin(phi2)
      + Math.cos(phi1) * Math.cos(phi2) * Math.cos(lam2 - lam1)
    ))
  );
  if (d < 1e-9) return [[lat1, lon1], [lat2, lon2]];

  const pts = [];
  for (let i = 0; i <= steps; i++) {
    const f = i / steps;
    const A = Math.sin((1 - f) * d) / Math.sin(d);
    const B = Math.sin(f * d) / Math.sin(d);
    const x = A * Math.cos(phi1) * Math.cos(lam1) + B * Math.cos(phi2) * Math.cos(lam2);
    const y = A * Math.cos(phi1) * Math.sin(lam1) + B * Math.cos(phi2) * Math.sin(lam2);
    const z = A * Math.sin(phi1)                  + B * Math.sin(phi2);
    const lat = toDeg(Math.atan2(z, Math.sqrt(x * x + y * y)));
    const lon = toDeg(Math.atan2(y, x));
    pts.push([lat, lon]);
  }
  return pts;
}

/** Splits a gc path at the antimeridian (±180°) to avoid horizontal line artifacts */
function splitAtAntimeridian(pts) {
  const segments = [];
  let current = [pts[0]];
  for (let i = 1; i < pts.length; i++) {
    const prev = current[current.length - 1];
    const curr = pts[i];
    if (Math.abs(curr[1] - prev[1]) > 180) {
      segments.push(current);
      current = [curr];
    } else {
      current.push(curr);
    }
  }
  segments.push(current);
  return segments;
}

function LiveCounter({ lastUpdate, refreshing }) {
  return (
    <div className="flex items-center gap-2 text-xs text-gray-400">
      {refreshing
        ? <span className="animate-pulse text-yellow-400">Actualizando...</span>
        : lastUpdate && <span>Última actualización: {lastUpdate.toLocaleTimeString()}</span>
      }
    </div>
  );
}

export default function FlightMap() {
  const { t }                       = useTranslation();
  const [flights, setFlights]       = useState([]);
  const [selected, setSelected]     = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError]           = useState(null);
  const intervalRef                 = useRef(null);

  async function fetchLive() {
    setRefreshing(true);
    setError(null);
    try {
      const res = await axios.get(`${API_BASE}/flights/live`);
      setFlights(res.data);
      setLastUpdate(new Date());
    } catch (e) {
      setError("No se pudo conectar al servidor.");
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    fetchLive();
    intervalRef.current = setInterval(fetchLive, 30000);
    return () => clearInterval(intervalRef.current);
  }, []);

  // Airports involved in current live flights
  const activeAirports = new Set(
    flights.flatMap(f => [f.origin, f.destination])
  );

  return (
    <div className="flex flex-col flex-1 bg-[#0d1117]" style={{ minHeight: 0 }}>

      {/* ── Header ─────────────────────────────────────────────── */}
      <div
        className="flex items-center justify-between px-6 py-3 border-b"
        style={{ background: NAVY, borderColor: "#1e2a3a" }}
      >
        <div className="flex items-center gap-3">
          <span className="text-2xl">✈</span>
          <div>
            <h1 className="text-white font-bold text-lg tracking-wide">
              RPA Flight Tracker
            </h1>
            <p className="text-blue-300 text-xs">
              {flights.length} vuelo{flights.length !== 1 ? "s" : ""} en el aire ahora mismo
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
            ↻ Actualizar
          </button>
        </div>
      </div>

      {/* ── Error banner ──────────────────────────────────────── */}
      {error && (
        <div className="bg-red-900/80 text-red-200 text-sm px-6 py-2 text-center">
          {error}
        </div>
      )}

      {/* ── Map + Side panel ────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden" style={{ minHeight: 0 }}>

        {/* Map */}
        <div className="flex-1 relative">
          <MapContainer
            center={[20, 10]}
            zoom={2}
            minZoom={2}
            maxZoom={8}
            style={{ width: "100%", height: "100%", minHeight: "400px", background: "#0d1117" }}
            zoomControl={true}
          >
            {/* Dark tile layer */}
            <TileLayer
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
              attribution='&copy; <a href="https://carto.com">CARTO</a>'
              subdomains="abcd"
              maxZoom={20}
            />

            {/* Airport dots */}
            {Object.entries(AIRPORT_COORDS).map(([code, [lat, lon]]) => (
              <Marker
                key={code}
                position={[lat, lon]}
                icon={makeAirportIcon(activeAirports.has(code))}
              >
                <Tooltip permanent={false} direction="top" offset={[0, -6]}>
                  <span className="text-xs font-bold">{code}</span>
                  <span className="text-xs text-gray-400 ml-1">
                    {AIRPORT_NAMES[code]}
                  </span>
                </Tooltip>
              </Marker>
            ))}

            {/* Flight paths + plane markers */}
            {flights.map(flight => {
              const oc = AIRPORT_COORDS[flight.origin];
              const dc = AIRPORT_COORDS[flight.destination];
              if (!oc || !dc) return null;

              const pathPts  = gcPath(oc[0], oc[1], dc[0], dc[1]);
              const segments = splitAtAntimeridian(pathPts);

              const isSelected = selected?.id === flight.id;
              const isDemo     = !!flight.is_demo;

              const pathColor  = isSelected ? GOLD : (isDemo ? GOLD : "#8B1B3D");
              const pathOpacity = isSelected ? 0.9 : 0.45;

              return (
                <div key={flight.id}>
                  {/* Great-circle path */}
                  {segments.map((seg, si) => (
                    <Polyline
                      key={si}
                      positions={seg}
                      pathOptions={{
                        color:   pathColor,
                        weight:  isSelected ? 2 : 1.2,
                        opacity: pathOpacity,
                        dashArray: isDemo ? "6 4" : undefined,
                      }}
                    />
                  ))}

                  {/* Plane icon */}
                  <Marker
                    position={[flight.lat, flight.lon]}
                    icon={makePlaneIcon(flight.heading, isDemo)}
                    eventHandlers={{ click: () => setSelected(flight) }}
                  >
                    <Tooltip direction="top" offset={[0, -16]}>
                      <div className="text-xs">
                        <div className="font-bold text-white">
                          {flight.origin} → {flight.destination}
                          {isDemo && <span className="ml-1 text-yellow-400">[DEMO]</span>}
                        </div>
                        <div className="text-gray-300">
                          Vuelo #{flight.id} &nbsp;·&nbsp;
                          {Math.round(flight.fraction * 100)}% completado
                        </div>
                      </div>
                    </Tooltip>
                  </Marker>
                </div>
              );
            })}
          </MapContainer>

          {/* Legend */}
          <div
            className="absolute bottom-4 left-4 rounded-xl p-3 text-xs z-[1000] space-y-1.5"
            style={{ background: "rgba(10,31,68,0.92)", border: "1px solid #1e3a5f" }}
          >
            <div className="text-gray-300 font-semibold mb-1">Leyenda</div>
            <div className="flex items-center gap-2 text-gray-300">
              <span style={{ color: WINE, fontSize: 16 }}>✈</span>
              <span>Vuelo activo</span>
            </div>
            <div className="flex items-center gap-2 text-gray-300">
              <span style={{ color: GOLD, fontSize: 16 }}>✈</span>
              <span>Vuelo demo</span>
            </div>
            <div className="flex items-center gap-2 text-gray-300">
              <span className="inline-block w-3 h-3 rounded-full" style={{ background: GOLD }} />
              <span>Aeropuerto activo</span>
            </div>
          </div>

          {/* No flights message */}
          {!refreshing && flights.length === 0 && !error && (
            <div
              className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2
                         rounded-2xl p-6 text-center z-[1000]"
              style={{ background: "rgba(10,31,68,0.92)", border: "1px solid #1e3a5f" }}
            >
              <div className="text-4xl mb-2">🛫</div>
              <p className="text-white font-semibold">Sin vuelos en el aire ahora mismo</p>
              <p className="text-gray-400 text-sm mt-1">
                Los vuelos aparecerán cuando coincida con el horario de salida y duración.
              </p>
            </div>
          )}
        </div>

        {/* ── Side panel ────────────────────────────────────────── */}
        <div
          className="w-72 flex flex-col overflow-y-auto"
          style={{ background: "#0d1117", borderLeft: "1px solid #1e2a3a" }}
        >
          <div className="px-4 py-3 border-b" style={{ borderColor: "#1e2a3a" }}>
            <p className="text-white font-semibold text-sm">Vuelos activos</p>
          </div>

          {flights.length === 0 && !refreshing && (
            <div className="flex-1 flex items-center justify-center text-gray-600 text-sm px-4 text-center">
              No hay vuelos en el aire en este momento.
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
                className="w-full text-left px-4 py-3 border-b transition-colors"
                style={{
                  borderColor: "#1e2a3a",
                  background: isSelected ? "rgba(139,27,61,0.2)" : "transparent",
                }}
              >
                {/* Route */}
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className="font-bold text-base"
                    style={{ color: isDemo ? GOLD : WINE }}
                  >
                    {flight.origin}
                  </span>
                  <span className="text-gray-500 text-xs">→</span>
                  <span
                    className="font-bold text-base"
                    style={{ color: isDemo ? GOLD : WINE }}
                  >
                    {flight.destination}
                  </span>
                  {isDemo && (
                    <span
                      className="ml-auto text-xs px-1.5 py-0.5 rounded font-bold"
                      style={{ background: GOLD, color: NAVY }}
                    >
                      DEMO
                    </span>
                  )}
                </div>

                {/* Info */}
                <div className="text-xs text-gray-400 space-y-0.5">
                  <div>Vuelo #{flight.id} &nbsp;·&nbsp; {flight.aircraft_type || "—"}</div>
                  <div>Salida: {flight.departure_time} UTC &nbsp;·&nbsp; {flight.duration_hours}h</div>
                </div>

                {/* Progress bar */}
                <div className="mt-2">
                  <div className="flex justify-between text-xs text-gray-500 mb-1">
                    <span>{AIRPORT_NAMES[flight.origin] || flight.origin}</span>
                    <span>{pct}%</span>
                    <span>{AIRPORT_NAMES[flight.destination] || flight.destination}</span>
                  </div>
                  <div className="w-full h-1 rounded-full" style={{ background: "#1e2a3a" }}>
                    <div
                      className="h-1 rounded-full transition-all"
                      style={{
                        width: `${pct}%`,
                        background: isDemo ? GOLD : WINE,
                      }}
                    />
                  </div>
                </div>

                {/* Expanded detail */}
                {isSelected && (
                  <div
                    className="mt-3 rounded-lg p-3 text-xs space-y-1"
                    style={{ background: "rgba(10,31,68,0.6)", border: "1px solid #1e3a5f" }}
                  >
                    <div className="flex justify-between">
                      <span className="text-gray-400">Posición</span>
                      <span className="text-white font-mono">
                        {flight.lat}°, {flight.lon}°
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Rumbo</span>
                      <span className="text-white">{flight.heading}°</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Nodo dueño</span>
                      <span className="text-white capitalize">{flight.node_owner}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Tiempo restante</span>
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
