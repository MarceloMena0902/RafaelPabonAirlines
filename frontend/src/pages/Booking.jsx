/**
 * Booking.jsx
 * ─────────────────────────────────────────────────────────────
 * Página de compra de pasaje.
 *
 * Funcionalidades:
 *   • "Estoy comprando desde" → ciudad → nodo más cercano
 *   • Mapa de asientos realista por modelo de avión
 *   • Panel lateral con datos del asiento + pasajero
 *   • PDF boarding pass + wallet download tras confirmar
 */
import { useEffect, useState, useRef } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { getFlightById, getReservationsForFlight, createReservation, searchCities, getNearestNode } from "../api";
import SeatMap from "../components/SeatMap";

// ── Aeronaves ─────────────────────────────────────────────────
const AIRCRAFT_INFO = {
  1: { type_code: "A380", model: "Airbus A380-800",      first_class_seats: 10, economy_seats: 439 },
  2: { type_code: "B777", model: "Boeing 777-300ER",     first_class_seats: 10, economy_seats: 300 },
  3: { type_code: "A350", model: "Airbus A350-900",      first_class_seats: 12, economy_seats: 250 },
  4: { type_code: "B787", model: "Boeing 787-9 Dreamliner", first_class_seats: 8, economy_seats: 220 },
};
const aircraftFor = (id) => AIRCRAFT_INFO[(id - 1) % 4 + 1] || AIRCRAFT_INFO[1];

// Flags por país (fallback genérico 🌐)
const COUNTRY_FLAGS = {
  "Bolivia": "🇧🇴", "Colombia": "🇨🇴", "Perú": "🇵🇪", "Chile": "🇨🇱",
  "Argentina": "🇦🇷", "Brasil": "🇧🇷", "Venezuela": "🇻🇪", "México": "🇲🇽",
  "Uruguay": "🇺🇾", "Paraguay": "🇵🇾", "Ecuador": "🇪🇨", "Cuba": "🇨🇺",
  "Guatemala": "🇬🇹", "Costa Rica": "🇨🇷", "Panamá": "🇵🇦",
  "EE.UU.": "🇺🇸", "USA": "🇺🇸", "United States": "🇺🇸", "Canada": "🇨🇦", "Canadá": "🇨🇦",
  "Ucrania": "🇺🇦", "Ukraine": "🇺🇦",
  "Rusia": "🇷🇺", "Russia": "🇷🇺",
  "España": "🇪🇸", "France": "🇫🇷", "Francia": "🇫🇷",
  "United Kingdom": "🇬🇧", "Reino Unido": "🇬🇧",
  "Alemania": "🇩🇪", "Germany": "🇩🇪",
  "Italia": "🇮🇹", "Italy": "🇮🇹",
  "Países Bajos": "🇳🇱", "Netherlands": "🇳🇱",
  "Turquía": "🇹🇷", "Turkey": "🇹🇷",
  "Egipto": "🇪🇬", "Egypt": "🇪🇬",
  "Sudáfrica": "🇿🇦", "South Africa": "🇿🇦",
  "Kenia": "🇰🇪", "Kenya": "🇰🇪",
  "Nigeria": "🇳🇬", "Etiopía": "🇪🇹", "Marruecos": "🇲🇦",
  "EAU": "🇦🇪", "UAE": "🇦🇪",
  "Arabia Saudita": "🇸🇦",
  "India": "🇮🇳", "Pakistan": "🇵🇰", "Bangladesh": "🇧🇩",
  "China": "🇨🇳", "Japón": "🇯🇵", "Japan": "🇯🇵",
  "Corea del Sur": "🇰🇷", "South Korea": "🇰🇷",
  "Tailandia": "🇹🇭", "Thailand": "🇹🇭",
  "Singapur": "🇸🇬", "Singapore": "🇸🇬",
  "Indonesia": "🇮🇩", "Filipinas": "🇵🇭", "Philippines": "🇵🇭",
  "Vietnam": "🇻🇳", "Malasia": "🇲🇾", "Malaysia": "🇲🇾",
  "Australia": "🇦🇺", "Nueva Zelanda": "🇳🇿", "New Zealand": "🇳🇿",
  "Polonia": "🇵🇱", "Poland": "🇵🇱",
  "Rumania": "🇷🇴", "Romania": "🇷🇴",
  "Suecia": "🇸🇪", "Sweden": "🇸🇪",
  "Noruega": "🇳🇴", "Norway": "🇳🇴",
  "Finlandia": "🇫🇮", "Finland": "🇫🇮",
  "Dinamarca": "🇩🇰", "Denmark": "🇩🇰",
  "Portugal": "🇵🇹",
  "Grecia": "🇬🇷", "Greece": "🇬🇷",
  "Israel": "🇮🇱", "Iran": "🇮🇷", "Iraq": "🇮🇶",
  "Kazakhstan": "🇰🇿",
};
function countryFlag(country) {
  return COUNTRY_FLAGS[country] || "🌐";
}

const NODE_META = {
  beijing: { label: "Pekín",   flag: "🇨🇳", color: "bg-red-50 border-red-200 text-red-700" },
  ukraine: { label: "Ucrania", flag: "🇺🇦", color: "bg-blue-50 border-blue-200 text-blue-700" },
  lapaz:   { label: "La Paz",  flag: "🇧🇴", color: "bg-green-50 border-green-200 text-green-700" },
};

const API_BASE = "http://localhost:8000";

export default function Booking() {
  const { id }     = useParams();
  const [params]   = useSearchParams();
  const navigate   = useNavigate();
  const { t }      = useTranslation();
  const cabinClass = params.get("cabin") || "ECONOMY";

  const [flight,        setFlight]        = useState(null);
  const [taken,         setTaken]         = useState([]);
  const [seat,          setSeat]          = useState(null);
  const [passport,      setPassport]      = useState("");
  const [paxName,       setPaxName]       = useState("");
  const [buyerCity,     setBuyerCity]     = useState({
    label: "La Paz", country: "Bolivia", node: "lapaz",
    node_label: "La Paz", node_flag: "🇧🇴",
  });
  const [cityQuery,     setCityQuery]     = useState("");
  const [cityOpen,      setCityOpen]      = useState(false);
  const [citySuggestions, setCitySuggestions] = useState([]);
  const [citySearching,   setCitySearching]   = useState(false);
  const [loading,       setLoading]       = useState(true);
  const [submitting,    setSubmitting]    = useState(false);
  const [result,        setResult]        = useState(null);
  const [error,         setError]         = useState(null);
  const debounceRef = useRef(null);
  const cityDropRef = useRef(null);

  useEffect(() => {
    Promise.all([getFlightById(id), getReservationsForFlight(id)])
      .then(([fl, reservations]) => {
        setFlight(fl);
        setTaken(reservations.map((r) => r.seat_number));
      })
      .catch(() => setError({ type: "generic" }))
      .finally(() => setLoading(false));
  }, [id]);

  const aircraft = flight ? aircraftFor(flight.aircraft_id) : null;

  // Debounced city search via API
  useEffect(() => {
    if (cityQuery.trim().length < 2) {
      setCitySuggestions([]);
      return;
    }
    clearTimeout(debounceRef.current);
    setCitySearching(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const results = await searchCities(cityQuery.trim(), 12);
        setCitySuggestions(results);
      } catch {
        setCitySuggestions([]);
      } finally {
        setCitySearching(false);
      }
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [cityQuery]);

  // Close city dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (cityDropRef.current && !cityDropRef.current.contains(e.target))
        setCityOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleCitySelect = async (cityResult) => {
    // cityResult = { city, country, lat, lon } from search API
    setCitySearching(true);
    try {
      const nodeInfo = await getNearestNode(cityResult.city);
      setBuyerCity({
        label:      cityResult.city,
        country:    cityResult.country,
        node:       nodeInfo.node,
        node_label: nodeInfo.node_label,
        node_flag:  nodeInfo.node_flag,
      });
    } catch {
      // fallback: keep current
    } finally {
      setCitySearching(false);
      setCityOpen(false);
      setCityQuery("");
      setCitySuggestions([]);
    }
  };

  const handleConfirm = async (e) => {
    e.preventDefault();
    if (!seat || !passport) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await createReservation({
        flight_id:          parseInt(id),
        passenger_passport: passport.toUpperCase(),
        seat_number:        seat,
        cabin_class:        cabinClass,
      });
      setResult(res);
    } catch (err) {
      if (err.response?.status === 503)
        setError({ type: "503", detail: err.response.data.detail });
      else if (err.response?.status === 409)
        setError({ type: "conflict", msg: err.response.data.detail });
      else
        setError({ type: "generic" });
    } finally {
      setSubmitting(false);
    }
  };

  /* ── Pantalla de carga ───────────────────────────────────── */
  if (loading) return (
    <div className="flex justify-center items-center h-64">
      <div className="animate-spin w-10 h-10 border-4 border-brand-wine border-t-transparent rounded-full" />
    </div>
  );

  /* ── Confirmación exitosa ────────────────────────────────── */
  if (result) return (
    <div className="max-w-lg mx-auto px-4 py-16 text-center">
      <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <svg className="w-8 h-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      </div>
      <h2 className="text-2xl font-bold text-gray-900 mb-2">{t("booking.success")}</h2>

      <div className="bg-white border border-gray-200 rounded-2xl p-6 text-left mt-6 space-y-2 text-sm">
        <p><strong>{t("booking.tx_id")}:</strong>
          <span className="font-mono text-brand-wine ml-1">{result.transaction_id}</span>
        </p>
        <p><strong>Asiento:</strong> {result.seat_number} · {result.cabin_class}</p>
        <p><strong>Precio:</strong> USD {result.price_paid}</p>
        <p><strong>{t("booking.node")}:</strong> {NODE_META[result.node_origin]?.flag} {NODE_META[result.node_origin]?.label || result.node_origin}</p>
        <p><strong>Comprado desde:</strong> {countryFlag(buyerCity.country)} {buyerCity.label}{buyerCity.country ? `, ${buyerCity.country}` : ""}</p>
        <p><strong>{t("booking.vector_clock")}:</strong>
          <span className="font-mono ml-1 text-xs bg-gray-100 px-2 py-0.5 rounded">
            {result.vector_clock}
          </span>
        </p>
      </div>

      {/* Botones de ticket */}
      <div className="mt-6 flex flex-col sm:flex-row gap-3 justify-center">
        <a
          href={`${API_BASE}/reservations/${result.transaction_id}/ticket`}
          target="_blank"
          rel="noreferrer"
          className="flex items-center justify-center gap-2 bg-brand-wine text-white font-semibold px-6 py-3 rounded-full hover:bg-brand-wine2 transition-colors text-sm"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          Ver boarding pass
        </a>
        <a
          href={`${API_BASE}/reservations/${result.transaction_id}/wallet`}
          className="flex items-center justify-center gap-2 border border-brand-wine text-brand-wine font-semibold px-6 py-3 rounded-full hover:bg-brand-wine/5 transition-colors text-sm"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Descargar (Wallet)
        </a>
      </div>

      <button onClick={() => navigate("/")}
        className="mt-4 text-gray-500 text-sm hover:text-gray-700 transition-colors">
        Volver al inicio
      </button>
    </div>
  );

  /* ── Formulario de reserva ───────────────────────────────── */
  // Support both API-driven buyerCity (has node_label) and legacy format
  const nodeMeta = buyerCity.node_label
    ? { label: buyerCity.node_label, flag: buyerCity.node_flag, color: "bg-blue-50 border-blue-200 text-blue-700" }
    : (NODE_META[buyerCity.node] || NODE_META.lapaz);

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">

      {/* ── Encabezado del vuelo ─────────────────────────── */}
      {flight && (
        <div className="bg-white border border-gray-200 rounded-2xl p-5 mb-5">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-3 text-2xl font-bold text-gray-900 flex-1">
              <span>{flight.origin}</span>
              <span className="text-brand-wine">→</span>
              <span>{flight.destination}</span>
            </div>
            <div className="text-sm text-gray-500">
              <div>{flight.flight_date} · {String(flight.departure_time).slice(0, 5)} · Puerta {flight.gate}</div>
              <div className="font-medium text-gray-700">{aircraft?.model} · {flight.duration_hours}h</div>
            </div>
            <div className="text-right">
              <div className="text-xl font-bold text-brand-wine">
                USD {cabinClass === "FIRST" ? flight.price_first : flight.price_economy}
              </div>
              <div className="text-xs text-gray-400">{cabinClass === "FIRST" ? "Primera clase" : "Económica"}</div>
            </div>
          </div>
        </div>
      )}

      {/* ── Selector "Estoy comprando desde" ─────────────── */}
      <div className="bg-white border border-gray-200 rounded-2xl p-5 mb-5">
        <div className="flex items-start sm:items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2 shrink-0">
            <svg className="w-5 h-5 text-brand-wine" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span className="text-sm font-semibold text-gray-700 whitespace-nowrap">{t("booking.from_city")}:</span>
          </div>

          {/* City search dropdown */}
          <div ref={cityDropRef} className="relative flex-1 min-w-48">
            <button
              type="button"
              onClick={() => { setCityOpen(o => !o); }}
              className="w-full flex items-center gap-2 border border-gray-200 rounded-xl px-4 py-2.5 text-sm hover:border-brand-wine transition-colors text-left bg-white"
            >
              <span className="text-lg">{countryFlag(buyerCity.country)}</span>
              <span className="flex-1 font-medium text-gray-900">
                {buyerCity.label}{buyerCity.country ? `, ${buyerCity.country}` : ""}
              </span>
              <span className="text-gray-400 text-xs">▾</span>
            </button>

            {cityOpen && (
              <div className="absolute z-50 mt-1 w-80 bg-white border border-gray-200 rounded-xl shadow-xl overflow-hidden">
                <div className="p-2 border-b border-gray-100">
                  <input
                    autoFocus
                    type="text"
                    value={cityQuery}
                    onChange={e => setCityQuery(e.target.value)}
                    placeholder="Buscar cualquier ciudad del mundo..."
                    className="w-full px-3 py-2 text-sm bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:border-brand-wine"
                  />
                </div>
                <div className="max-h-60 overflow-y-auto">
                  {citySearching && (
                    <div className="px-4 py-3 text-xs text-gray-400 flex items-center gap-2">
                      <span className="animate-spin inline-block w-3 h-3 border-2 border-brand-wine border-t-transparent rounded-full" />
                      Buscando...
                    </div>
                  )}
                  {!citySearching && cityQuery.length >= 2 && citySuggestions.length === 0 && (
                    <div className="px-4 py-3 text-xs text-gray-400">Sin resultados para "{cityQuery}"</div>
                  )}
                  {!citySearching && cityQuery.length < 2 && (
                    <div className="px-4 py-3 text-xs text-gray-400">Escribe al menos 2 letras para buscar</div>
                  )}
                  {citySuggestions.map(c => (
                    <button
                      key={`${c.city}-${c.country}`}
                      type="button"
                      onClick={() => handleCitySelect(c)}
                      className="w-full px-4 py-2.5 flex items-center gap-2 hover:bg-gray-50 text-sm text-left"
                    >
                      <span>{countryFlag(c.country)}</span>
                      <span className="flex-1">
                        <span className="font-medium text-gray-900">{c.city}</span>
                        <span className="text-gray-400 ml-1 text-xs">{c.country}</span>
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Nodo asignado */}
          <div className={`flex items-center gap-2 text-sm font-semibold px-4 py-2 rounded-full border ${nodeMeta.color}`}>
            <span className="w-2 h-2 rounded-full bg-current opacity-70" />
            {nodeMeta.flag} Nodo: {nodeMeta.label}
          </div>
        </div>

        {/* Explicación distribuida */}
        <p className="text-xs text-gray-400 mt-2 ml-7">
          Las bases de datos se mantienen sincronizadas · delay máx. 10 segundos ·
          Nodo responsable: <span className="font-medium text-gray-600">{nodeMeta.label}</span>
        </p>
      </div>

      {/* ── Cabina + panel de datos ───────────────────────── */}
      <div className="grid lg:grid-cols-3 gap-5">

        {/* Mapa de asientos (2/3 del ancho) */}
        <div className="lg:col-span-2 bg-white border border-gray-200 rounded-2xl p-5">
          <h3 className="font-semibold text-gray-700 mb-4 flex items-center gap-2">
            <svg className="w-4 h-4 text-brand-wine" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
            </svg>
            {t("booking.seat_map")} — {aircraft?.model}
          </h3>
          <SeatMap
            aircraft={aircraft}
            takenSeats={taken}
            selectedSeat={seat}
            cabinClass={cabinClass}
            onSelect={setSeat}
          />
        </div>

        {/* Panel lateral con datos */}
        <div className="bg-white border border-gray-200 rounded-2xl p-5">

          {/* Detalle del asiento seleccionado */}
          <div className="bg-gray-50 rounded-xl p-4 mb-4 border border-gray-200">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">Asiento</span>
              {seat && (
                <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
                  taken.includes(seat) ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"
                }`}>
                  {taken.includes(seat) ? t("booking.seat_taken") : t("booking.seat_free")}
                </span>
              )}
            </div>
            <div className="text-3xl font-bold text-brand-wine">
              {seat || <span className="text-gray-300 text-xl">—</span>}
            </div>
            {seat && (
              <div className="text-xs text-gray-500 mt-1">
                {cabinClass === "FIRST" ? "Primera Clase" : "Clase Económica"}
              </div>
            )}
          </div>

          {/* Formulario */}
          <form onSubmit={handleConfirm} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t("booking.passenger")} *
              </label>
              <input
                type="text"
                required
                placeholder="Ej: LA28169216"
                value={passport}
                onChange={(e) => setPassport(e.target.value)}
                className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-brand-wine font-mono"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t("booking.pax_name")}
              </label>
              <input
                type="text"
                placeholder="Nombre completo"
                value={paxName}
                onChange={(e) => setPaxName(e.target.value)}
                className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-brand-wine"
              />
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700">
                {error.type === "503" ? t("error.503") : error.msg || t("error.generic")}
              </div>
            )}

            {!seat && (
              <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                Selecciona un asiento en el mapa de cabina
              </p>
            )}

            <button
              type="submit"
              disabled={!seat || !passport || submitting}
              className="w-full bg-brand-wine text-white py-3 rounded-full font-semibold hover:bg-brand-wine2 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {submitting ? "Procesando..." : t("booking.confirm")}
            </button>

            <button
              type="button"
              onClick={() => navigate(-1)}
              className="w-full text-gray-500 text-sm hover:text-gray-700 transition-colors py-1"
            >
              {t("booking.cancel")}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
