import { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { getFlights } from "../api";

const NODE_COLORS = {
  beijing: "bg-red-100 text-red-700",
  ukraine: "bg-blue-100 text-blue-700",
  lapaz:   "bg-green-100 text-green-700",
};
const NODE_LABELS = { beijing: "Pekín", ukraine: "Ucrania", lapaz: "La Paz" };

// Capacidad total por aircraft_id (mismo que Booking.jsx)
const AIRCRAFT_CAP = {
  1: { eco: 439, first: 10 },
  2: { eco: 300, first: 10 },
  3: { eco: 250, first: 12 },
  4: { eco: 220, first:  8 },
};
const capFor = (id, cabin) => {
  const c = AIRCRAFT_CAP[(id - 1) % 4 + 1] || AIRCRAFT_CAP[1];
  return cabin === "FIRST" ? c.first : c.eco;
};

// Barra de ocupación
function OccupancyBar({ total, available }) {
  if (!total) return null;
  const sold    = Math.max(0, total - available);
  const pctSold = Math.round((sold / total) * 100);
  const color   = pctSold >= 90 ? "bg-red-500" : pctSold >= 70 ? "bg-amber-500" : "bg-green-500";
  return (
    <div className="mt-1.5">
      <div className="flex justify-between text-[10px] text-gray-400 mb-0.5">
        <span>{pctSold}% ocupado</span>
        <span>{available} libres</span>
      </div>
      <div className="h-1.5 w-full bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pctSold}%` }} />
      </div>
    </div>
  );
}

// Tarjeta de vuelo individual
function FlightCard({ f, cabin, onSelect, isSelected }) {
  const avail = cabin === "FIRST" ? f.available_first : f.available_economy;
  const price = cabin === "FIRST" ? f.price_first     : f.price_economy;
  const total = capFor(f.aircraft_id, cabin);
  const sold  = total - avail;
  const pct   = Math.round((sold / total) * 100);

  return (
    <div
      onClick={() => avail > 0 && onSelect(f)}
      className={`relative bg-white border-2 rounded-2xl p-4 transition-all cursor-pointer
        ${avail <= 0 ? "opacity-50 cursor-not-allowed border-gray-200" :
          isSelected
            ? "border-brand-wine shadow-lg shadow-brand-wine/20 ring-2 ring-brand-wine/40"
            : "border-gray-200 hover:border-brand-wine hover:shadow-md"}`}
    >
      {isSelected && (
        <div className="absolute top-2 right-2 bg-brand-wine text-white text-[10px] font-bold px-2 py-0.5 rounded-full">
          Seleccionado
        </div>
      )}

      {/* Ruta */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xl font-bold text-gray-900">{f.origin}</span>
        <span className="text-brand-wine">→</span>
        <span className="text-xl font-bold text-gray-900">{f.destination}</span>
      </div>

      {/* Detalles */}
      <div className="text-xs text-gray-500 space-y-0.5 mb-2">
        <div>{f.flight_date} · {String(f.departure_time).slice(0,5)}</div>
        <div>{f.duration_hours}h · Puerta {f.gate}</div>
      </div>

      {/* Nodo */}
      <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${NODE_COLORS[f.node_owner] || "bg-gray-100 text-gray-600"}`}>
        {NODE_LABELS[f.node_owner] || f.node_owner}
      </span>

      {/* Precio */}
      <div className="mt-2 text-lg font-bold text-gray-900">USD {price}</div>

      {/* Barra de ocupación */}
      <OccupancyBar total={total} available={avail} />

      {avail <= 0 && (
        <div className="mt-2 text-xs font-semibold text-red-500">Agotado</div>
      )}
    </div>
  );
}

// Spinner
function Spinner() {
  return (
    <div className="flex justify-center py-12">
      <div className="w-9 h-9 border-4 border-brand-wine border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

// ── Componente principal ───────────────────────────────────────
export default function Search() {
  const [params]  = useSearchParams();
  const navigate  = useNavigate();

  const cabin      = params.get("cabin_class") || "ECONOMY";
  const tripType   = params.get("trip_type")   || "oneway";
  const isRound    = tripType === "roundtrip";

  const [outbound,  setOutbound]  = useState([]);
  const [returnFl,  setReturnFl]  = useState([]);
  const [loadOut,   setLoadOut]   = useState(true);
  const [loadRet,   setLoadRet]   = useState(false);
  const [errOut,    setErrOut]    = useState(false);
  const [errRet,    setErrRet]    = useState(false);
  const [selOut,    setSelOut]    = useState(null);
  const [selRet,    setSelRet]    = useState(null);

  // Vuelos de ida
  useEffect(() => {
    setLoadOut(true);
    setErrOut(false);
    const filters = {};
    if (params.get("origin"))      filters.origin      = params.get("origin");
    if (params.get("destination")) filters.destination = params.get("destination");
    if (params.get("flight_date")) filters.flight_date = params.get("flight_date");
    filters.cabin_class = cabin;

    getFlights(filters)
      .then(setOutbound)
      .catch(() => setErrOut(true))
      .finally(() => setLoadOut(false));
  }, [params.toString()]);

  // Vuelos de regreso (solo si ida y vuelta)
  useEffect(() => {
    if (!isRound) { setReturnFl([]); return; }
    const returnDate = params.get("return_date");
    const origin     = params.get("origin");
    const dest       = params.get("destination");
    if (!returnDate || !origin || !dest) { setReturnFl([]); return; }

    setLoadRet(true);
    setErrRet(false);
    getFlights({
      origin:      dest,
      destination: origin,
      flight_date: returnDate,
      cabin_class: cabin,
    })
      .then(setReturnFl)
      .catch(() => setErrRet(true))
      .finally(() => setLoadRet(false));
  }, [params.toString()]);

  const origin = params.get("origin");
  const dest   = params.get("destination");

  // Reservar vuelo seleccionado
  const handleBook = (flight) => {
    navigate(`/booking/${flight.id}?cabin=${cabin}`);
  };

  // ── Render ────────────────────────────────────────────────────
  return (
    <div className={`max-w-7xl mx-auto px-4 sm:px-6 py-8`}>

      {/* Encabezado */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Vuelos disponibles
            {origin && dest && (
              <span className="text-brand-wine ml-2">
                {origin} ⇄ {dest}
              </span>
            )}
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {isRound ? "Ida y vuelta" : "Solo ida"} · Clase {cabin === "FIRST" ? "Primera" : "Económica"}
          </p>
        </div>

        {/* Toggle ida / ida-y-vuelta */}
        <div className="flex bg-gray-100 rounded-xl p-1 gap-1">
          {[["oneway","Solo ida"],["roundtrip","Ida y vuelta"]].map(([val, label]) => {
            const active = tripType === val;
            const newP = new URLSearchParams(params);
            newP.set("trip_type", val);
            return (
              <button
                key={val}
                onClick={() => navigate(`/search?${newP.toString()}`)}
                className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all
                  ${active ? "bg-brand-wine text-white shadow" : "text-gray-600 hover:text-gray-900"}`}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Layout: una columna (ida) o dos columnas (ida+vuelta) ── */}
      <div className={`grid gap-6 ${isRound ? "grid-cols-1 lg:grid-cols-2" : "grid-cols-1"}`}>

        {/* ── Columna vuelos de IDA ──────────────────────────── */}
        <div>
          {isRound && (
            <h2 className="text-sm font-bold text-gray-700 uppercase tracking-wider mb-3 flex items-center gap-2">
              <span className="w-5 h-5 bg-brand-wine text-white rounded-full flex items-center justify-center text-xs">1</span>
              Vuelo de ida · {origin} → {dest}
            </h2>
          )}
          {loadOut && <Spinner />}
          {errOut && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-center text-red-700 text-sm">
              No se pudo conectar con el servidor.
            </div>
          )}
          {!loadOut && !errOut && outbound.length === 0 && (
            <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-gray-500 text-sm">
              No se encontraron vuelos.
            </div>
          )}
          <div className="space-y-3">
            {outbound.map((f) => (
              <FlightCard
                key={f.id} f={f} cabin={cabin}
                onSelect={isRound ? setSelOut : handleBook}
                isSelected={isRound && selOut?.id === f.id}
              />
            ))}
          </div>
        </div>

        {/* ── Columna vuelos de REGRESO (solo ida y vuelta) ──── */}
        {isRound && (
          <div>
            <h2 className="text-sm font-bold text-gray-700 uppercase tracking-wider mb-3 flex items-center gap-2">
              <span className="w-5 h-5 bg-brand-wine text-white rounded-full flex items-center justify-center text-xs">2</span>
              Vuelo de regreso · {dest} → {origin}
            </h2>

            {!params.get("return_date") && (
              <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-amber-700 text-sm text-center">
                Busca desde la página principal con fecha de regreso para ver vuelos de vuelta.
              </div>
            )}
            {loadRet && <Spinner />}
            {errRet && (
              <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-center text-red-700 text-sm">
                No se pudo conectar con el servidor.
              </div>
            )}
            {!loadRet && !errRet && params.get("return_date") && returnFl.length === 0 && (
              <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-gray-500 text-sm">
                No se encontraron vuelos de regreso.
              </div>
            )}
            <div className="space-y-3">
              {returnFl.map((f) => (
                <FlightCard
                  key={f.id} f={f} cabin={cabin}
                  onSelect={setSelRet}
                  isSelected={selRet?.id === f.id}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── Barra flotante para reservar ida y vuelta ──────────── */}
      {isRound && (selOut || selRet) && (
        <div className="fixed bottom-0 inset-x-0 bg-white border-t border-gray-200 shadow-2xl z-50 px-4 py-4">
          <div className="max-w-5xl mx-auto flex flex-wrap items-center justify-between gap-4">
            <div className="text-sm text-gray-700 space-y-0.5">
              {selOut && (
                <div><span className="font-semibold">Ida:</span> {selOut.origin} → {selOut.destination} · {selOut.flight_date} · USD {cabin === "FIRST" ? selOut.price_first : selOut.price_economy}</div>
              )}
              {selRet && (
                <div><span className="font-semibold">Regreso:</span> {selRet.origin} → {selRet.destination} · {selRet.flight_date} · USD {cabin === "FIRST" ? selRet.price_first : selRet.price_economy}</div>
              )}
            </div>
            <div className="flex gap-3">
              {selOut && (
                <button
                  onClick={() => handleBook(selOut)}
                  className="bg-brand-wine text-white font-semibold px-6 py-2.5 rounded-full hover:bg-brand-wine2 text-sm transition-colors"
                >
                  Reservar ida
                </button>
              )}
              {selRet && (
                <button
                  onClick={() => handleBook(selRet)}
                  className="bg-brand-navy text-white font-semibold px-6 py-2.5 rounded-full hover:opacity-90 text-sm transition-colors"
                >
                  Reservar regreso
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
