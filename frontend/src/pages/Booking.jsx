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
import { getFlightById, getSeatsForFlight, createReservation, cancelReservation, searchCities, getNearestNode, getPassenger } from "../api";
import SeatMap from "../components/SeatMap";

// ── Zonas horarias de aeropuertos (offsets correctos para abril 2026, con DST) ──
const AIRPORT_UTC = {
  ATL: -4,  // EDT (UTC-4 en verano)
  PEK: 8,   // CST
  DXB: 4,   // GST
  TYO: 9,   // JST
  LON: 1,   // BST (UTC+1 en verano)
  LAX: -7,  // PDT (UTC-7 en verano)
  PAR: 2,   // CEST (UTC+2 en verano)
  FRA: 2,   // CEST
  IST: 3,   // TRT
  SIN: 8,   // SGT
  MAD: 2,   // CEST
  AMS: 2,   // CEST
  DFW: -5,  // CDT (UTC-5 en verano)
  CAN: 8,   // CST
  SAO: -3,  // BRT
};

function localTime(depTimeStr, originCode, buyerUtcOffset) {
  if (!depTimeStr || !originCode || buyerUtcOffset === undefined) return null;
  const airportOff = AIRPORT_UTC[originCode];
  if (airportOff === undefined) return null;
  const [h, m] = String(depTimeStr).slice(0, 5).split(":").map(Number);
  const utcMin  = h * 60 + m - airportOff * 60;
  const locMin  = ((utcMin + buyerUtcOffset * 60) % 1440 + 1440) % 1440;
  return `${String(Math.floor(locMin / 60)).padStart(2, "0")}:${String(locMin % 60).padStart(2, "0")}`;
}

// ── Aeronaves ─────────────────────────────────────────────────
const AIRCRAFT_INFO = {
  1: { type_code: "A380", model: "Airbus A380-800",      first_class_seats: 10, economy_seats: 439 },
  2: { type_code: "B777", model: "Boeing 777-300ER",     first_class_seats: 10, economy_seats: 300 },
  3: { type_code: "A350", model: "Airbus A350-900",      first_class_seats: 12, economy_seats: 250 },
  4: { type_code: "B787", model: "Boeing 787-9 Dreamliner", first_class_seats: 8, economy_seats: 220 },
};
const aircraftFor = (id) => {
  if (id <= 6)  return AIRCRAFT_INFO[1];  // A380
  if (id <= 24) return AIRCRAFT_INFO[2];  // B777
  if (id <= 35) return AIRCRAFT_INFO[3];  // A350
  return AIRCRAFT_INFO[4];               // B787
};

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
// Cerca de la línea 97, después de countryFlag
function getBuyerCurrentTime(offset) {
  if (offset === undefined || offset === null) return "--:--";
  const ahora = new Date();
  const utc = ahora.getTime() + (ahora.getTimezoneOffset() * 60000);
  const horaLocal = new Date(utc + (3600000 * offset));
  return horaLocal.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
}
const NODE_META = {
  beijing: { label_key: "booking.node.beijing", flag: "🇨🇳", color: "bg-red-50 border-red-200 text-red-700" },
  ukraine: { label_key: "booking.node.ukraine", flag: "🇺🇦", color: "bg-blue-50 border-blue-200 text-blue-700" },
  lapaz:   { label_key: "booking.node.lapaz",   flag: "🇧🇴", color: "bg-green-50 border-green-200 text-green-700" },
};

const API_BASE = "http://localhost:8000";

export default function Booking() {
  const { id }     = useParams();
  const [params]   = useSearchParams();
  const navigate   = useNavigate();
  const { t }      = useTranslation();
  const cabinClass = params.get("cabin") || "ECONOMY";

  const [flight,        setFlight]        = useState(null);
  const [seatMap,       setSeatMap]       = useState({});   // { seatId: { status, passport, name } }
  const [seat,          setSeat]          = useState(null);
  const [passport,      setPassport]      = useState("");
  const [paxName,       setPaxName]       = useState("");
  const [buyerCity,     setBuyerCity]     = useState({
    label: "La Paz", country: "Bolivia", node: "lapaz",
    node_label: "La Paz", node_flag: "🇧🇴", utc_offset: -4,
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

  const loadSeats = async () => {
    const seats = await getSeatsForFlight(id);
    const map = {};
    seats.forEach(s => {
      map[s.seat_number] = {
        status:     s.status,
        passport:   s.passenger_passport,
        name:       s.passenger_name,
        transaction_id: s.transaction_id,
      };
    });
    setSeatMap(map);
  };
// Cerca de la línea 140, junto a los otros useState
const [currentTime, setCurrentTime] = useState("--:--");

// Añade este bloque antes del primer useEffect
useEffect(() => {
  const timer = setInterval(() => {
    setCurrentTime(getBuyerCurrentTime(buyerCity.utc_offset));
  }, 1000); // Actualiza cada segundo para que se vea real

  setCurrentTime(getBuyerCurrentTime(buyerCity.utc_offset));
  return () => clearInterval(timer);
}, [buyerCity.utc_offset]);

  useEffect(() => {
    Promise.all([getFlightById(id), getSeatsForFlight(id)])
      .then(([fl, seats]) => {
        setFlight(fl);
        const map = {};
        seats.forEach(s => {
          map[s.seat_number] = {
            status:   s.status,
            passport: s.passenger_passport,
            name:     s.passenger_name,
            transaction_id: s.transaction_id,
          };
        });
        setSeatMap(map);
      })
      .catch(() => setError({ type: "generic" }))
      .finally(() => setLoading(false));
  }, [id]);

  // Lookup de pasajero por pasaporte (para autocompletar en el popup)
  const lookupPassport = async (passport) => {
    try {
      return await getPassenger(passport);
    } catch {
      return null;
    }
  };

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
        utc_offset: nodeInfo.utc_offset ?? null,
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

  const handleBuy = async (seatId, passportVal, nameVal) => {
    setError(null);
    try {
      const res = await createReservation({
        flight_id:          parseInt(id),
        passenger_passport: passportVal,
        seat_number:        seatId,
        cabin_class:        cabinClass,
        status:             "CONFIRMED",
        buyer_node:         buyerCity.node,
      });
      setResult(res);
      await loadSeats();
    } catch (err) {
      if (err.response?.status === 503)
        setError({ type: "503", detail: err.response.data.detail });
      else if (err.response?.status === 409)
        setError({ type: "conflict", msg: err.response.data.detail });
      else
        setError({ type: "generic" });
      throw err; // re-throw so popup stays open
    }
  };

  const handleReserve = async (seatId, passportVal, nameVal) => {
    setError(null);
    try {
      const res = await createReservation({
        flight_id:          parseInt(id),
        passenger_passport: passportVal,
        seat_number:        seatId,
        cabin_class:        cabinClass,
        status:             "RESERVED",
        buyer_node:         buyerCity.node,
      });
      setResult(res);
      await loadSeats();
    } catch (err) {
      if (err.response?.status === 503)
        setError({ type: "503", detail: err.response.data.detail });
      else if (err.response?.status === 409)
        setError({ type: "conflict", msg: err.response.data.detail });
      else
        setError({ type: "generic" });
      throw err;
    }
  };

  /* ── Pantalla de carga ───────────────────────────────────── */
  if (loading) return (
    <div className="flex justify-center items-center h-64">
      <div className="animate-spin w-10 h-10 border-4 border-brand-wine border-t-transparent rounded-full" />
    </div>
  );

  /* ── Reserva exitosa (RESERVED) ─────────────────────────── */
  if (result && result.status === "RESERVED") return (
    <div className="max-w-lg mx-auto px-4 py-16 text-center">
      <div className="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <svg className="w-8 h-8 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      <h2 className="text-2xl font-bold text-gray-900 mb-1">{t("booking.reserved_title")}</h2>
      <p className="text-gray-500 text-sm mb-6">{t("booking.reserved_desc")}</p>

      <div className="bg-white border border-amber-200 rounded-2xl p-6 text-left space-y-2 text-sm">
        <p><strong>{t("booking.tx_id")}:</strong>
          <span className="font-mono text-amber-700 ml-1">{result.transaction_id}</span>
        </p>
        <p><strong>{t("booking.seat_label")}:</strong> {result.seat_number} · {result.cabin_class}</p>
        <p><strong>{t("booking.node")}:</strong> {NODE_META[result.node_origin]?.flag} {t(NODE_META[result.node_origin]?.label_key) || result.node_origin}</p>
      </div>

      <button onClick={() => navigate("/")}
        className="mt-6 text-gray-500 text-sm hover:text-gray-700 transition-colors">
        {t("booking.back_home")}
      </button>
    </div>
  );

  /* ── Compra exitosa (CONFIRMED) ──────────────────────────── */
  if (result && result.status !== "RESERVED") return (
    <div className="max-w-2xl mx-auto px-4 py-12">
      {/* Cabecera */}
      <div className="text-center mb-8">
        <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg className="w-8 h-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h2 className="text-2xl font-bold text-gray-900">{t("booking.success")}</h2>
        <p className="text-gray-500 text-sm mt-1">{t("booking.success_desc")}</p>
      </div>

      {/* Ticket visual */}
      <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden shadow-md mb-6">
        {/* Franja superior de color */}
        <div className="h-2 bg-brand-wine" />

        <div className="p-6 grid sm:grid-cols-2 gap-6">
          {/* Vuelo */}
          <div>
            <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">{t("booking.flight_info")}</p>
            <div className="flex items-center gap-3 mb-2">
              <span className="text-3xl font-bold text-gray-900">{flight?.origin}</span>
              <span className="text-brand-wine text-xl">→</span>
              <span className="text-3xl font-bold text-gray-900">{flight?.destination}</span>
            </div>
            <p className="text-sm text-gray-600 mb-1">
              {flight?.flight_date} ·{" "}
              <span className="font-semibold text-gray-800">
                  {currentTime}
                </span>
                <span className="text-xs text-gray-400 ml-1.5">
                  {t("booking.local_time")} {buyerCity.label}
                </span>
              <span className="text-xs text-gray-400 ml-1">({buyerCity.label})</span>
            </p>
            <p className="text-xs text-gray-500">{aircraft?.model} · {flight?.duration_hours}h · {t("booking.gate")} {flight?.gate}</p>
          </div>

          {/* Pasajero */}
          <div>
            <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">{t("booking.passenger_info")}</p>
            <p className="text-sm font-semibold text-gray-800 mb-1">{t("booking.passport_label")}: {result.passenger_passport}</p>
            <p className="text-sm text-gray-600 mb-1">
              {t("booking.seat_label")}: <span className="font-semibold">{result.seat_number}</span>
              {" · "}
              {cabinClass === "FIRST" ? t("booking.first_class") : t("booking.economy_class")}
            </p>
            <p className="text-sm text-gray-600">{t("booking.bought_from")}: {countryFlag(buyerCity.country)} {buyerCity.label}</p>
          </div>
        </div>

        {/* Footer del ticket */}
        <div className="bg-gray-50 border-t border-gray-100 px-6 py-3 flex flex-wrap items-center justify-between gap-2 text-xs text-gray-500">
          <span>{t("booking.tx_id")}: <span className="font-mono text-brand-wine">{result.transaction_id}</span></span>
          <span className="font-bold text-gray-700">USD {result.price_paid}</span>
        </div>
      </div>

      {/* Nodo origen */}
      <div className={`flex items-center gap-2 px-4 py-2 rounded-xl border text-sm mb-6 w-fit mx-auto ${NODE_META[result.node_origin]?.color}`}>
        {NODE_META[result.node_origin]?.flag} {t(NODE_META[result.node_origin]?.label_key) || result.node_origin}
        <span className="text-xs opacity-60">· {t("booking.node")}</span>
      </div>

      {/* Botones de ticket */}
      <div className="flex flex-col sm:flex-row gap-3 justify-center">
        <a
          href={`${API_BASE}/reservations/${result.transaction_id}/ticket`}
          target="_blank"
          rel="noreferrer"
          className="flex items-center justify-center gap-2 bg-brand-wine text-white font-semibold px-6 py-3 rounded-full hover:bg-brand-wine2 transition-colors text-sm"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          {t("booking.boarding_pass")}
        </a>
        <a
          href={`${API_BASE}/reservations/${result.transaction_id}/wallet`}
          target="_blank"
          rel="noreferrer"
          download
          className="flex items-center justify-center gap-2 border border-brand-wine text-brand-wine font-semibold px-6 py-3 rounded-full hover:bg-brand-wine/5 transition-colors text-sm"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          {t("booking.wallet")}
        </a>
      </div>

      <div className="text-center mt-4">
        <button onClick={() => navigate("/")}
          className="text-gray-500 text-sm hover:text-gray-700 transition-colors">
          {t("booking.back_home")}
        </button>
      </div>
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
              <div>
                {flight.flight_date} ·{" "}
                <span className="font-semibold text-gray-800">
                  {currentTime}
                </span>
                <span className="text-xs text-gray-400 ml-1.5">
                  {t("booking.local_time")} {buyerCity.label}
                </span>
              </div>
              <div className="font-medium text-gray-700">
                {aircraft?.model} · {flight.duration_hours}h · {t("booking.gate")} {flight.gate}
              </div>
            </div>
            <div className="text-right">
              <div className="text-xl font-bold text-brand-wine">
                USD {cabinClass === "FIRST" ? flight.price_first : flight.price_economy}
              </div>
              <div className="text-xs text-gray-400">{cabinClass === "FIRST" ? t("booking.first_class") : t("booking.economy_class")}</div>
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
                    placeholder={t("booking.search_city")}
                    className="w-full px-3 py-2 text-sm bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:border-brand-wine"
                  />
                </div>
                <div className="max-h-60 overflow-y-auto">
                  {citySearching && (
                    <div className="px-4 py-3 text-xs text-gray-400 flex items-center gap-2">
                      <span className="animate-spin inline-block w-3 h-3 border-2 border-brand-wine border-t-transparent rounded-full" />
                      {t("booking.city_searching")}
                    </div>
                  )}
                  {!citySearching && cityQuery.length >= 2 && citySuggestions.length === 0 && (
                    <div className="px-4 py-3 text-xs text-gray-400">{t("booking.city_no_results")} "{cityQuery}"</div>
                  )}
                  {!citySearching && cityQuery.length < 2 && (
                    <div className="px-4 py-3 text-xs text-gray-400">{t("booking.city_hint")}</div>
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
            {nodeMeta.flag} {t("booking.node_prefix")}: {nodeMeta.label_key ? t(nodeMeta.label_key) : nodeMeta.label}
          </div>
        </div>

        {/* Explicación distribuida */}
        <p className="text-xs text-gray-400 mt-2 ml-7">
          {t("booking.db_sync")} ·
          {t("booking.node_resp")}: <span className="font-medium text-gray-600">{nodeMeta.label_key ? t(nodeMeta.label_key) : nodeMeta.label}</span>
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
            seatMap={seatMap}
            cabinClass={cabinClass}
            onBuy={handleBuy}
            onReserve={handleReserve}
            lookupPassport={lookupPassport}
          />
        </div>

        {/* Panel lateral informativo */}
        <div className="bg-white border border-gray-200 rounded-2xl p-5 flex flex-col gap-4">

          {/* Instrucción */}
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-700">
            <p className="font-semibold mb-1">{t("booking.how_to_buy")}</p>
            <ol className="list-decimal list-inside space-y-1 text-xs">
              <li>{t("booking.how1")}</li>
              <li>{t("booking.how2")}</li>
              <li>{t("booking.how3")}</li>
              <li>{t("booking.how4")}</li>
            </ol>
          </div>

          {/* Estadísticas del vuelo */}
          {flight && (
            <div className="bg-gray-50 rounded-xl p-4 border border-gray-100 text-xs space-y-2">
              <p className="font-bold text-gray-600 uppercase tracking-wider mb-2">{t("booking.availability")}</p>
              <div className="flex justify-between">
                <span className="text-gray-500">{t("booking.eco_free")}</span>
                <span className="font-semibold text-gray-800">{flight.available_economy}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">{t("booking.first_free")}</span>
                <span className="font-semibold text-gray-800">{flight.available_first}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">{t("booking.seats_sold")}</span>
                <span className="font-semibold text-green-600">
                  {Object.values(seatMap).filter(s => s.status === "CONFIRMED").length}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">{t("booking.seats_reserved")}</span>
                <span className="font-semibold text-amber-600">
                  {Object.values(seatMap).filter(s => s.status === "RESERVED").length}
                </span>
              </div>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700">
              {error.type === "503" ? t("error.503") : error.msg || t("error.generic")}
            </div>
          )}

          <button
            type="button"
            onClick={() => navigate(-1)}
            className="w-full text-gray-500 text-sm hover:text-gray-700 transition-colors py-2 border border-gray-200 rounded-xl"
          >
            {t("booking.cancel")}
          </button>
        </div>
      </div>
    </div>
  );
}
