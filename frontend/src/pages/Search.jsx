import { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { getFlights, getSuggestedRoute } from "../api";

const NODE_COLORS = {
  beijing: "bg-red-100 text-red-700",
  ukraine: "bg-blue-100 text-blue-700",
  lapaz:   "bg-green-100 text-green-700",
};
const NODE_LABEL_KEYS = {
  beijing: "search.node.beijing",
  ukraine: "search.node.ukraine",
  lapaz:   "search.node.lapaz",
};

// Capacidad total por aircraft_id — misma lógica que Booking.jsx (IDs 1-50)
const AIRCRAFT_CAP = {
  1: { eco: 439, first: 10 },  // A380
  2: { eco: 300, first: 10 },  // B777
  3: { eco: 250, first: 12 },  // A350
  4: { eco: 220, first:  8 },  // B787
};
function acKey(id) {
  if (id <= 6)  return 1;
  if (id <= 24) return 2;
  if (id <= 35) return 3;
  return 4;
}
const capFor = (id, cabin) => {
  const c = AIRCRAFT_CAP[acKey(id)] || AIRCRAFT_CAP[4];
  return cabin === "FIRST" ? c.first : c.eco;
};

const PAGE_SIZE = 8;

// Barra de ocupación
function OccupancyBar({ total, available, t }) {
  if (!total) return null;
  const sold    = Math.max(0, total - available);
  const pctSold = Math.round((sold / total) * 100);
  const color   = pctSold >= 90 ? "bg-red-500" : pctSold >= 70 ? "bg-amber-500" : "bg-green-500";
  return (
    <div className="mt-1.5">
      <div className="flex justify-between text-[10px] text-gray-400 mb-0.5">
        <span>{pctSold}% {t("search.pct_occupied")}</span>
        <span>{available} {t("search.pct_free")}</span>
      </div>
      <div className="h-1.5 w-full bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pctSold}%` }} />
      </div>
    </div>
  );
}

// Tarjeta de vuelo individual
function FlightCard({ f, cabin, onSelect, isSelected }) {
  const { t } = useTranslation();
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
          {t("search.selected_label")}
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
        <div>{f.duration_hours}h · {t("search.gate")} {f.gate}</div>
      </div>

      {/* Nodo */}
      <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${NODE_COLORS[f.node_owner] || "bg-gray-100 text-gray-600"}`}>
        {t(NODE_LABEL_KEYS[f.node_owner]) || f.node_owner}
      </span>

      {/* Precio */}
      <div className="mt-2 text-lg font-bold text-gray-900">USD {price}</div>

      {/* Barra de ocupación */}
      <OccupancyBar total={total} available={avail} t={t} />

      {avail <= 0 && (
        <div className="mt-2 text-xs font-semibold text-red-500">{t("search.sold_out")}</div>
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

// ── Paginación ─────────────────────────────────────────────────
function Pagination({ total, page, onPage }) {
  const { t } = useTranslation();
  const pages = Math.ceil(total / PAGE_SIZE);
  if (pages <= 1) return null;
  return (
    <div className="flex items-center justify-between mt-4 px-1">
      <button
        onClick={() => onPage(p => Math.max(0, p - 1))}
        disabled={page === 0}
        className="px-4 py-1.5 rounded-lg text-sm font-medium border border-gray-200 text-gray-600
                   disabled:opacity-30 hover:border-brand-wine hover:text-brand-wine transition-colors"
      >
        ← {t("search.prev")}
      </button>
      <span className="text-xs text-gray-500">
        {t("search.page")} <span className="font-semibold text-gray-800">{page + 1}</span> {t("search.of")} {pages}
        &nbsp;·&nbsp; {total} {t("search.flights_count")}
      </span>
      <button
        onClick={() => onPage(p => Math.min(pages - 1, p + 1))}
        disabled={page >= pages - 1}
        className="px-4 py-1.5 rounded-lg text-sm font-medium border border-gray-200 text-gray-600
                   disabled:opacity-30 hover:border-brand-wine hover:text-brand-wine transition-colors"
      >
        {t("search.next")} →
      </button>
    </div>
  );
}

// ── Panel de sugerencia Dijkstra ───────────────────────────────
function SuggestionPanel({ suggestion, cabin, onBook }) {
  const { t } = useTranslation();
  if (!suggestion) return null;

  return (
    <div className="mt-4 bg-amber-50 border-2 border-amber-200 rounded-2xl p-5">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-amber-600 text-lg">✦</span>
        <h3 className="font-bold text-amber-800 text-sm">
          {t("search.suggestion_title") || "Ruta sugerida con escalas"}
        </h3>
        <span className="text-xs text-amber-500 bg-amber-100 rounded-full px-2 py-0.5">
          {suggestion.hops === 0
            ? (t("search.direct") || "Directo")
            : `${suggestion.hops} ${t("search.stopover") || "escala(s)"}`}
        </span>
      </div>

      {/* Resumen de ruta */}
      <div className="flex items-center gap-1 text-sm font-semibold text-amber-900 mb-4 flex-wrap">
        {suggestion.path.map((ap, i) => (
          <span key={ap} className="flex items-center gap-1">
            <span className="bg-white border border-amber-300 rounded-lg px-2 py-0.5">{ap}</span>
            {i < suggestion.path.length - 1 && <span className="text-amber-400">→</span>}
          </span>
        ))}
        <span className="ml-2 text-xs font-normal text-amber-600">
          · USD {suggestion.total_cost} · {suggestion.total_hours}h
        </span>
      </div>

      {/* Segmentos */}
      <div className="space-y-3">
        {suggestion.segments.map((seg, i) => {
          const fl = seg.nearest_flight;
          return (
            <div key={i} className="bg-white border border-amber-200 rounded-xl p-4">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div>
                  <div className="flex items-center gap-2 font-bold text-gray-800">
                    <span>{seg.from}</span>
                    <span className="text-amber-400">→</span>
                    <span>{seg.to}</span>
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">
                    {seg.hours}h · USD {seg.cost}
                  </div>
                </div>

                {fl ? (
                  <div className="text-right">
                    <div className="text-xs text-gray-500">
                      {fl.flight_date}
                      {fl.flight_date !== suggestion.requested_date && (
                        <span className="ml-1 text-amber-500">
                          ({t("search.nearest_date") || "fecha más cercana"})
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-gray-500">{fl.departure_time} · {fl.aircraft_type}</div>
                    <div className="font-bold text-gray-900 text-sm">USD {fl.price}</div>
                    <div className={`text-xs ${fl.available <= 0 ? "text-red-500" : "text-green-600"}`}>
                      {fl.available <= 0
                        ? (t("search.sold_out") || "Agotado")
                        : `${fl.available} ${t("search.pct_free") || "disponibles"}`}
                    </div>
                    {fl.available > 0 && (
                      <button
                        onClick={() => onBook(fl.flight_id, cabin)}
                        className="mt-1 bg-brand-wine text-white text-xs font-semibold px-3 py-1 rounded-full hover:bg-brand-wine2 transition-colors"
                      >
                        {t("search.book_leg") || "Reservar tramo"}
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="text-xs text-red-400 italic">
                    {t("search.no_flight_segment") || "Sin vuelo disponible para este tramo"}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Componente principal ───────────────────────────────────────
export default function Search() {
  const { t }     = useTranslation();
  const [params]  = useSearchParams();
  const navigate  = useNavigate();

  const cabin      = params.get("cabin_class") || "ECONOMY";
  const tripType   = params.get("trip_type")   || "oneway";
  const isRound    = tripType === "roundtrip";

  const [outbound,    setOutbound]    = useState([]);
  const [returnFl,    setReturnFl]    = useState([]);
  const [loadOut,     setLoadOut]     = useState(true);
  const [loadRet,     setLoadRet]     = useState(false);
  const [errOut,      setErrOut]      = useState(false);
  const [errRet,      setErrRet]      = useState(false);
  const [selOut,      setSelOut]      = useState(null);
  const [selRet,      setSelRet]      = useState(null);
  const [pageOut,     setPageOut]     = useState(0);
  const [pageRet,     setPageRet]     = useState(0);
  const [suggestion,  setSuggestion]  = useState(null);
  const [loadSuggest, setLoadSuggest] = useState(false);

  // Vuelos de ida
  useEffect(() => {
    setLoadOut(true);
    setErrOut(false);
    setPageOut(0);
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

  // Sugerencia Dijkstra (solo si no hay vuelos directos)
  useEffect(() => {
    setSuggestion(null);
    if (loadOut) return;
    const o = params.get("origin");
    const d = params.get("destination");
    const dt = params.get("flight_date");
    if (!o || !d || !dt || outbound.length > 0) return;
    setLoadSuggest(true);
    getSuggestedRoute(o, d, dt, cabin)
      .then(s => setSuggestion(s))
      .catch(() => setSuggestion(null))
      .finally(() => setLoadSuggest(false));
  }, [outbound, loadOut]);

  // Vuelos de regreso (solo si ida y vuelta)
  useEffect(() => {
    if (!isRound) { setReturnFl([]); return; }
    const returnDate = params.get("return_date");
    const origin     = params.get("origin");
    const dest       = params.get("destination");
    if (!returnDate || !origin || !dest) { setReturnFl([]); return; }

    setLoadRet(true);
    setErrRet(false);
    setPageRet(0);
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
            {t("search.available")}
            {origin && dest && (
              <span className="text-brand-wine ml-2">
                {origin} ⇄ {dest}
              </span>
            )}
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {isRound ? t("search.roundtrip") : t("search.oneway")} · {t("search.class")} {cabin === "FIRST" ? t("search.class_first") : t("search.class_eco")}
          </p>
        </div>

        {/* Toggle ida / ida-y-vuelta */}
        <div className="flex bg-gray-100 rounded-xl p-1 gap-1">
          {[["oneway", t("search.oneway")],["roundtrip", t("search.roundtrip")]].map(([val, label]) => {
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
              {t("search.outbound_leg")} · {origin} → {dest}
            </h2>
          )}
          {loadOut && <Spinner />}
          {errOut && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-center text-red-700 text-sm">
              {t("search.server_error")}
            </div>
          )}
          {!loadOut && !errOut && outbound.length === 0 && (
            <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-gray-500 text-sm">
              {t("search.no_results")}
              {loadSuggest && (
                <div className="mt-3 text-xs text-amber-600 flex items-center justify-center gap-2">
                  <div className="w-4 h-4 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
                  {t("search.finding_route") || "Buscando ruta alternativa..."}
                </div>
              )}
            </div>
          )}
          {!loadOut && !errOut && outbound.length === 0 && (
            <SuggestionPanel
              suggestion={suggestion}
              cabin={cabin}
              onBook={(flightId, cl) => navigate(`/booking/${flightId}?cabin=${cl}`)}
            />
          )}
          <div className="space-y-3">
            {outbound.slice(pageOut * PAGE_SIZE, (pageOut + 1) * PAGE_SIZE).map((f) => (
              <FlightCard
                key={f.id} f={f} cabin={cabin}
                onSelect={isRound ? setSelOut : handleBook}
                isSelected={isRound && selOut?.id === f.id}
              />
            ))}
          </div>
          <Pagination total={outbound.length} page={pageOut} onPage={setPageOut} />
        </div>

        {/* ── Columna vuelos de REGRESO (solo ida y vuelta) ──── */}
        {isRound && (
          <div>
            <h2 className="text-sm font-bold text-gray-700 uppercase tracking-wider mb-3 flex items-center gap-2">
              <span className="w-5 h-5 bg-brand-wine text-white rounded-full flex items-center justify-center text-xs">2</span>
              {t("search.return_leg")} · {dest} → {origin}
            </h2>

            {!params.get("return_date") && (
              <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-amber-700 text-sm text-center">
                {t("search.no_return_hint")}
              </div>
            )}
            {loadRet && <Spinner />}
            {errRet && (
              <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-center text-red-700 text-sm">
                {t("search.server_error")}
              </div>
            )}
            {!loadRet && !errRet && params.get("return_date") && returnFl.length === 0 && (
              <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-gray-500 text-sm">
                {t("search.no_results")}
              </div>
            )}
            <div className="space-y-3">
              {returnFl.slice(pageRet * PAGE_SIZE, (pageRet + 1) * PAGE_SIZE).map((f) => (
                <FlightCard
                  key={f.id} f={f} cabin={cabin}
                  onSelect={setSelRet}
                  isSelected={selRet?.id === f.id}
                />
              ))}
            </div>
            <Pagination total={returnFl.length} page={pageRet} onPage={setPageRet} />
          </div>
        )}
      </div>

      {/* ── Barra flotante para reservar ida y vuelta ──────────── */}
      {isRound && (selOut || selRet) && (
        <div className="fixed bottom-0 inset-x-0 bg-white border-t border-gray-200 shadow-2xl z-50 px-4 py-4">
          <div className="max-w-5xl mx-auto flex flex-wrap items-center justify-between gap-4">
            <div className="text-sm text-gray-700 space-y-0.5">
              {selOut && (
                <div><span className="font-semibold">{t("search.outbound_label")}:</span> {selOut.origin} → {selOut.destination} · {selOut.flight_date} · USD {cabin === "FIRST" ? selOut.price_first : selOut.price_economy}</div>
              )}
              {selRet && (
                <div><span className="font-semibold">{t("search.return_label")}:</span> {selRet.origin} → {selRet.destination} · {selRet.flight_date} · USD {cabin === "FIRST" ? selRet.price_first : selRet.price_economy}</div>
              )}
            </div>
            <div className="flex gap-3">
              {selOut && (
                <button
                  onClick={() => handleBook(selOut)}
                  className="bg-brand-wine text-white font-semibold px-6 py-2.5 rounded-full hover:bg-brand-wine2 text-sm transition-colors"
                >
                  {t("search.book_outbound")}
                </button>
              )}
              {selRet && (
                <button
                  onClick={() => handleBook(selRet)}
                  className="bg-brand-navy text-white font-semibold px-6 py-2.5 rounded-full hover:opacity-90 text-sm transition-colors"
                >
                  {t("search.book_return")}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
