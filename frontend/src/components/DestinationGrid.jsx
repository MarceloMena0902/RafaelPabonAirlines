/**
 * DestinationGrid.jsx
 * ────────────────────
 * Cuadrícula de destinos estilo Qatar Airways.
 * Muestra ciudades con gradientes de colores vibrantes + código IATA + precio.
 * (No usa imágenes externas — gradientes CSS para compatibilidad offline)
 */
import { useNavigate } from "react-router-dom";

const DESTINATIONS = [
  {
    code: "DXB", city: "Dubái",      country: "EAU",
    gradient: "from-amber-900 via-orange-600 to-yellow-400",
    emoji: "🌆", price: "desde $850",
  },
  {
    code: "PAR", city: "París",      country: "Francia",
    gradient: "from-blue-900 via-indigo-700 to-purple-500",
    emoji: "🗼", price: "desde $620",
  },
  {
    code: "TYO", city: "Tokio",      country: "Japón",
    gradient: "from-rose-900 via-red-600 to-pink-400",
    emoji: "⛩️", price: "desde $980",
  },
  {
    code: "LON", city: "Londres",    country: "Reino Unido",
    gradient: "from-slate-900 via-gray-700 to-slate-500",
    emoji: "🎡", price: "desde $590",
  },
  {
    code: "SIN", city: "Singapur",   country: "Singapur",
    gradient: "from-teal-900 via-cyan-700 to-emerald-500",
    emoji: "🦁", price: "desde $760",
  },
  {
    code: "SAO", city: "São Paulo",  country: "Brasil",
    gradient: "from-green-900 via-lime-700 to-yellow-500",
    emoji: "🌎", price: "desde $410",
  },
];

export default function DestinationGrid({ onDestinationSelect }) {
  const navigate = useNavigate();

  const handleClick = (code) => {
    if (onDestinationSelect) {
      onDestinationSelect(code);
    } else {
      navigate(`/search?destination=${code}&cabin_class=ECONOMY`);
    }
  };

  return (
    <section className="max-w-7xl mx-auto px-4 sm:px-6 py-14">
      {/* Título */}
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-900">
          Lugares que creemos le enamorarán
        </h2>
        <p className="text-gray-500 mt-1 text-sm">
          Descubra destinos extraordinarios con RafaelPabón Airlines
        </p>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {DESTINATIONS.map((dest) => (
          <button
            key={dest.code}
            onClick={() => handleClick(dest.code)}
            className="group relative overflow-hidden rounded-2xl aspect-[3/4] text-left focus:outline-none focus:ring-2 focus:ring-brand-wine"
          >
            {/* Fondo gradiente */}
            <div className={`absolute inset-0 bg-gradient-to-b ${dest.gradient} transition-transform duration-500 group-hover:scale-105`} />

            {/* Overlay oscuro en hover */}
            <div className="absolute inset-0 bg-black/20 group-hover:bg-black/30 transition-colors" />

            {/* Emoji decorativo */}
            <div className="absolute top-3 left-3 text-3xl opacity-80 group-hover:scale-110 transition-transform">
              {dest.emoji}
            </div>

            {/* Contenido texto */}
            <div className="absolute bottom-0 left-0 right-0 p-3 bg-gradient-to-t from-black/70 to-transparent">
              <p className="text-white font-bold text-sm leading-tight">{dest.city}</p>
              <p className="text-white/70 text-xs">{dest.country}</p>
              <p className="text-brand-gold font-semibold text-xs mt-1">{dest.price}</p>
            </div>

            {/* Badge IATA */}
            <div className="absolute top-3 right-3 bg-white/20 backdrop-blur-sm text-white text-xs font-bold px-2 py-0.5 rounded-full">
              {dest.code}
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}
