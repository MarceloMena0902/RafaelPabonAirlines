import { useEffect, useState } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { getFlightById, getReservationsForFlight, createReservation } from "../api";
import SeatMap from "../components/SeatMap";

const AIRCRAFT_INFO = {
  1: { type_code: "A380", first_class_seats: 10, economy_seats: 439 },
  2: { type_code: "B777", first_class_seats: 10, economy_seats: 300 },
  3: { type_code: "A350", first_class_seats: 12, economy_seats: 250 },
  4: { type_code: "B787", first_class_seats:  8, economy_seats: 220 },
};
const aircraftFor = (id) => AIRCRAFT_INFO[(id - 1) % 4 + 1] || AIRCRAFT_INFO[1];

const API_BASE = "http://localhost:8000";

export default function Booking() {
  const { id }     = useParams();
  const [params]   = useSearchParams();
  const navigate   = useNavigate();
  const { t }      = useTranslation();
  const cabinClass = params.get("cabin") || "ECONOMY";

  const [flight,     setFlight]     = useState(null);
  const [taken,      setTaken]      = useState([]);
  const [seat,       setSeat]       = useState(null);
  const [passport,   setPassport]   = useState("");
  const [loading,    setLoading]    = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [result,     setResult]     = useState(null);
  const [error,      setError]      = useState(null);

  useEffect(() => {
    Promise.all([getFlightById(id), getReservationsForFlight(id)])
      .then(([fl, reservations]) => {
        setFlight(fl);
        setTaken(reservations.map((r) => r.seat_number));
      })
      .catch(() => setError({ type: "generic" }))
      .finally(() => setLoading(false));
  }, [id]);

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

  if (loading) return (
    <div className="flex justify-center items-center h-64">
      <div className="animate-spin w-10 h-10 border-4 border-brand-wine border-t-transparent rounded-full" />
    </div>
  );

  /* ── Confirmación exitosa ─────────────────────────────────── */
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
        <p><strong>{t("booking.node")}:</strong> {result.node_origin}</p>
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
          className="bg-brand-wine text-white font-semibold px-6 py-3 rounded-full hover:bg-brand-wine2 transition-colors text-sm"
        >
          Ver boarding pass PDF
        </a>
        <a
          href={`${API_BASE}/reservations/${result.transaction_id}/wallet`}
          className="border border-brand-wine text-brand-wine font-semibold px-6 py-3 rounded-full hover:bg-brand-wine/5 transition-colors text-sm"
        >
          Descargar ticket
        </a>
      </div>

      <button onClick={() => navigate("/")}
        className="mt-4 text-gray-500 text-sm hover:text-gray-700 transition-colors">
        Volver al inicio
      </button>
    </div>
  );

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">{t("booking.title")}</h1>

      {flight && (
        <div className="bg-white border border-gray-200 rounded-2xl p-5 mb-6">
          <div className="flex items-center gap-4 text-xl font-bold text-gray-900">
            <span>{flight.origin}</span>
            <span className="text-brand-wine">→</span>
            <span>{flight.destination}</span>
            <span className="text-base font-normal text-gray-500">
              {flight.flight_date} · {String(flight.departure_time).slice(0, 5)}
            </span>
          </div>
          <div className="text-sm text-gray-500 mt-1">
            Avión {aircraftFor(flight.aircraft_id).type_code} · {flight.duration_hours}h · Puerta {flight.gate}
          </div>
          <div className="mt-2 font-bold text-brand-wine text-lg">
            USD {cabinClass === "FIRST" ? flight.price_first : flight.price_economy}
          </div>
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-8">
        <div>
          <h3 className="font-semibold text-gray-700 mb-3">{t("booking.seat_map")}</h3>
          <SeatMap
            aircraft={flight ? aircraftFor(flight.aircraft_id) : null}
            takenSeats={taken}
            selectedSeat={seat}
            cabinClass={cabinClass}
            onSelect={setSeat}
          />
          {seat && (
            <p className="mt-2 text-sm text-brand-wine font-medium">
              {t("booking.selected_seat")}: <strong>{seat}</strong>
            </p>
          )}
        </div>

        <div>
          <form onSubmit={handleConfirm} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t("booking.passenger")}
              </label>
              <input
                type="text"
                required
                placeholder="Ej: LA28169216"
                value={passport}
                onChange={(e) => setPassport(e.target.value)}
                className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-brand-wine"
              />
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700">
                {error.type === "503" ? t("error.503") : error.msg || t("error.generic")}
              </div>
            )}

            <button
              type="submit"
              disabled={!seat || !passport || submitting}
              className="w-full bg-brand-wine text-white py-3 rounded-full font-semibold hover:bg-brand-wine2 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {submitting ? "Procesando..." : t("booking.confirm")}
            </button>

            <button type="button" onClick={() => navigate(-1)}
              className="w-full text-gray-500 text-sm hover:text-gray-700 transition-colors">
              {t("booking.cancel")}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
