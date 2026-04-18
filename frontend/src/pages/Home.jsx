import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import CitySelector from "../components/CitySelector";
import DestinationGrid from "../components/DestinationGrid";
import useNodeMap from "../hooks/useNodeMap";

const NODE_LABEL_KEYS = { beijing: "search.node.beijing", ukraine: "search.node.ukraine", lapaz: "search.node.lapaz" };
const NODE_ICONS  = { beijing: "🇨🇳", ukraine: "🇺🇦", lapaz: "🇧🇴" };

export default function Home() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [origin,     setOrigin]     = useState("");
  const [dest,       setDest]       = useState("");
  const [date,       setDate]       = useState("");
  const [returnDate, setReturnDate] = useState("");
  const [cabin,      setCabin]      = useState("ECONOMY");
  const [tripType,   setTripType]   = useState("oneway");
  const { nodeMap, nodeStatus } = useNodeMap();

  const nodeOf   = (code) => nodeMap[code];
  const onlineOf = (code) => nodeStatus[nodeMap[code]];

  // Nodos involucrados en la ruta seleccionada (pueden ser el mismo)
  const involvedNodes = [...new Set([
    origin && nodeOf(origin),
    dest   && nodeOf(dest),
  ].filter(Boolean))];

  const handleSearch = (e) => {
    e.preventDefault();
    const p = new URLSearchParams();
    if (origin) p.set("origin",      origin);
    if (dest)   p.set("destination", dest);
    if (date)   p.set("flight_date", date);
    p.set("cabin_class", cabin);
    p.set("trip_type", tripType);
    if (tripType === "roundtrip" && returnDate) p.set("return_date", returnDate);
    navigate(`/search?${p.toString()}`);
  };

  return (
    <main>
      {/* ── Hero ─────────────────────────────────────────────── */}
      <section className="relative bg-hero-sky overflow-hidden">
        {/* Avión SVG decorativo */}
        <div className="absolute inset-0 flex items-center justify-end opacity-20 pointer-events-none">
          <svg viewBox="0 0 200 80" className="w-3/4 max-w-2xl text-white fill-current" xmlns="http://www.w3.org/2000/svg">
            <path d="M180,35 L20,10 L30,35 L20,60 L180,35 Z" />
            <path d="M80,35 L50,15 L55,35 L50,55 Z" />
            <path d="M110,35 L95,28 L97,35 L95,42 Z" />
          </svg>
        </div>

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 py-24 md:py-32">
          <div className="max-w-xl">
            <p className="text-brand-gold font-semibold text-sm uppercase tracking-widest mb-3">
              {t("home.cp_badge")}
            </p>
            <h1 className="text-4xl md:text-5xl font-bold text-white leading-tight mb-4">
              {t("hero.title")}
            </h1>
            <p className="text-white/70 text-lg mb-8">
              {t("hero.subtitle")}
            </p>
            <button
              onClick={() => document.getElementById("search-widget")?.scrollIntoView({ behavior: "smooth" })}
              className="bg-brand-wine text-white font-semibold px-8 py-3 rounded-full hover:bg-brand-wine2 transition-colors"
            >
              {t("home.book_now")}
            </button>
          </div>
        </div>
      </section>

      {/* ── Widget de búsqueda ────────────────────────────────── */}
      <section id="search-widget" className="max-w-5xl mx-auto px-4 sm:px-6 -mt-8 relative z-10">
        <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100">
          <h2 className="text-lg font-bold text-gray-900 mb-4">{t("home.search_title")}</h2>

          {/* Toggle tipo de viaje */}
          <div className="flex bg-gray-100 rounded-xl p-1 gap-1 mb-5 w-fit">
            {[["oneway", t("home.oneway")],["roundtrip", t("home.roundtrip")]].map(([val, label]) => (
              <button
                key={val} type="button"
                onClick={() => setTripType(val)}
                className={`px-5 py-1.5 rounded-lg text-sm font-medium transition-all
                  ${tripType === val ? "bg-brand-wine text-white shadow" : "text-gray-600 hover:text-gray-900"}`}
              >
                {label}
              </button>
            ))}
          </div>

          <form onSubmit={handleSearch}>
            <div className={`grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4 ${tripType === "roundtrip" ? "lg:grid-cols-5" : "lg:grid-cols-4"}`}>
              {/* Origen */}
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                  {t("search.origin")}
                </label>
                <CitySelector value={origin} onChange={setOrigin} placeholder={t("home.placeholder_origin")} />
              </div>
              {/* Destino */}
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                  {t("search.destination")}
                </label>
                <CitySelector value={dest} onChange={setDest} placeholder={t("home.placeholder_dest")} />
              </div>
              {/* Fecha ida */}
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                  {tripType === "roundtrip" ? t("home.date_out") : t("search.date")}
                </label>
                <input
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-brand-wine"
                />
              </div>
              {/* Fecha regreso (solo ida y vuelta) */}
              {tripType === "roundtrip" && (
                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                    {t("home.date_ret")}
                  </label>
                  <input
                    type="date"
                    value={returnDate}
                    min={date || undefined}
                    onChange={(e) => setReturnDate(e.target.value)}
                    className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-brand-wine"
                  />
                </div>
              )}
              {/* Clase */}
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                  {t("search.class")}
                </label>
                <select
                  value={cabin}
                  onChange={(e) => setCabin(e.target.value)}
                  className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-brand-wine bg-white"
                >
                  <option value="ECONOMY">{t("search.economy")}</option>
                  <option value="FIRST">{t("search.first")}</option>
                </select>
              </div>
            </div>
            {/* Panel de nodos involucrados */}
            {involvedNodes.length > 0 && (
              <div className="flex items-center gap-3 py-3 px-4 bg-gray-50 rounded-xl border border-gray-100 mb-2">
                <span className="text-xs text-gray-500 font-medium shrink-0">{t("home.active_nodes")}</span>
                <div className="flex gap-2 flex-wrap">
                  {involvedNodes.map((node) => {
                    const online = onlineOf(
                      Object.keys(nodeMap).find((k) => nodeMap[k] === node)
                    );
                    return (
                      <span
                        key={node}
                        className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full border ${
                          online === false
                            ? "bg-red-50 border-red-200 text-red-700"
                            : "bg-green-50 border-green-200 text-green-700"
                        }`}
                      >
                        <span className={`w-2 h-2 rounded-full ${online === false ? "bg-red-500" : "bg-green-500"}`} />
                        {NODE_ICONS[node]} {t(NODE_LABEL_KEYS[node])}
                        <span className="font-normal opacity-70">
                          {online === false ? `· ${t("home.node_down")}` : `· ${t("home.node_online")}`}
                        </span>
                      </span>
                    );
                  })}
                </div>
              </div>
            )}

            <div className="flex justify-end">
              <button
                type="submit"
                className="bg-brand-wine text-white font-semibold px-10 py-3 rounded-full hover:bg-brand-wine2 transition-colors text-sm"
              >
                {t("search.button")}
              </button>
            </div>
          </form>
        </div>
      </section>

      {/* ── Grid de destinos ──────────────────────────────────── */}
      <DestinationGrid />

      {/* ── Info sistema distribuido ──────────────────────────── */}
      <section className="bg-brand-navy text-white py-14">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 grid grid-cols-1 md:grid-cols-3 gap-8 text-center">
          <div>
            <div className="text-3xl font-bold text-brand-gold mb-2">CP</div>
            <div className="font-semibold mb-1">{t("home.cp_title")}</div>
            <div className="text-white/60 text-sm">{t("home.cp_desc")}</div>
          </div>
          <div>
            <div className="text-3xl font-bold text-brand-gold mb-2">VC</div>
            <div className="font-semibold mb-1">{t("home.vc_title")}</div>
            <div className="text-white/60 text-sm">{t("home.vc_desc")}</div>
          </div>
          <div>
            <div className="text-3xl font-bold text-brand-gold mb-2">IKJ</div>
            <div className="font-semibold mb-1">{t("home.ikj_title")}</div>
            <div className="text-white/60 text-sm">{t("home.ikj_desc")}</div>
          </div>
        </div>
      </section>

      {/* ── Footer ───────────────────────────────────────────── */}
      <footer className="bg-brand-navy border-t border-white/10 text-white/50 text-xs text-center py-6">
        © 2026 RafaelPabón Airlines · Sistema Distribuido CP · Relojes Vectoriales · IKJ
      </footer>
    </main>
  );
}
