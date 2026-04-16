import { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { getFlights } from "../api";

const NODE_COLORS = {
  beijing: "bg-red-100 text-red-700",
  ukraine: "bg-blue-100 text-blue-700",
  lapaz:   "bg-green-100 text-green-700",
};
const NODE_LABELS = { beijing: "Pekín", ukraine: "Ucrania", lapaz: "La Paz" };

export default function Search() {
  const [params]   = useSearchParams();
  const navigate   = useNavigate();
  const { t }      = useTranslation();
  const [flights,  setFlights]  = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState(false);
  const cabin = params.get("cabin_class") || "ECONOMY";

  useEffect(() => {
    setLoading(true);
    const filters = {};
    if (params.get("origin"))      filters.origin      = params.get("origin");
    if (params.get("destination")) filters.destination = params.get("destination");
    if (params.get("flight_date")) filters.flight_date = params.get("flight_date");
    if (cabin)                     filters.cabin_class = cabin;

    getFlights(filters)
      .then(setFlights)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [params.toString()]);

  const available = (f) =>
    cabin === "FIRST" ? f.available_first : f.available_economy;

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">
        Vuelos disponibles
        {params.get("origin") && params.get("destination") && (
          <span className="text-brand-wine ml-2">
            {params.get("origin")} → {params.get("destination")}
          </span>
        )}
      </h1>

      {loading && (
        <div className="flex justify-center py-20">
          <div className="w-10 h-10 border-4 border-brand-wine border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center text-red-700">
          No se pudo conectar con el servidor.
        </div>
      )}

      {!loading && !error && flights.length === 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-12 text-center text-gray-500">
          No se encontraron vuelos para los filtros seleccionados.
        </div>
      )}

      <div className="space-y-3">
        {flights.map((f) => {
          const seats = available(f);
          const price = cabin === "FIRST" ? f.price_first : f.price_economy;
          return (
            <div key={f.id}
              className="bg-white border border-gray-200 rounded-2xl p-5 hover:border-brand-wine hover:shadow-md transition-all"
            >
              <div className="flex flex-wrap items-center gap-4">
                {/* Ruta */}
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <span className="text-2xl font-bold text-gray-900">{f.origin}</span>
                  <span className="text-brand-wine text-xl">→</span>
                  <span className="text-2xl font-bold text-gray-900">{f.destination}</span>
                </div>

                {/* Info */}
                <div className="text-sm text-gray-500 space-y-0.5">
                  <div>{f.flight_date} · {String(f.departure_time).slice(0,5)}</div>
                  <div>{f.duration_hours}h · Puerta {f.gate}</div>
                </div>

                {/* Nodo */}
                <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${NODE_COLORS[f.node_owner] || "bg-gray-100 text-gray-600"}`}>
                  {NODE_LABELS[f.node_owner] || f.node_owner}
                </span>

                {/* Precio y botón */}
                <div className="text-right">
                  <div className="text-xl font-bold text-gray-900">USD {price}</div>
                  <div className="text-xs text-gray-400 mb-2">
                    {seats > 0 ? `${seats} asientos` : "Agotado"}
                  </div>
                  <button
                    disabled={seats <= 0}
                    onClick={() => navigate(`/booking/${f.id}?cabin=${cabin}`)}
                    className="bg-brand-wine text-white text-sm font-semibold px-5 py-2 rounded-full hover:bg-brand-wine2 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    Seleccionar
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
