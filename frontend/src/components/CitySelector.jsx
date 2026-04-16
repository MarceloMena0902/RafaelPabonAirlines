/**
 * CitySelector.jsx
 * ─────────────────
 * Dropdown buscable para seleccionar aeropuerto/ciudad.
 * Muestra: bandera emoji + ciudad + código IATA + badge de nodo.
 */
import { useState, useRef, useEffect } from "react";

export const AIRPORTS = [
  { code: "ATL", city: "Atlanta",      country: "EE.UU.",    flag: "🇺🇸", node: "lapaz"   },
  { code: "PEK", city: "Pekín",        country: "China",     flag: "🇨🇳", node: "beijing" },
  { code: "DXB", city: "Dubái",        country: "EAU",       flag: "🇦🇪", node: "ukraine" },
  { code: "TYO", city: "Tokio",        country: "Japón",     flag: "🇯🇵", node: "beijing" },
  { code: "LON", city: "Londres",      country: "R. Unido",  flag: "🇬🇧", node: "ukraine" },
  { code: "LAX", city: "Los Ángeles",  country: "EE.UU.",    flag: "🇺🇸", node: "lapaz"   },
  { code: "PAR", city: "París",        country: "Francia",   flag: "🇫🇷", node: "ukraine" },
  { code: "FRA", city: "Fráncfort",    country: "Alemania",  flag: "🇩🇪", node: "ukraine" },
  { code: "IST", city: "Estambul",     country: "Turquía",   flag: "🇹🇷", node: "ukraine" },
  { code: "SIN", city: "Singapur",     country: "Singapur",  flag: "🇸🇬", node: "beijing" },
  { code: "MAD", city: "Madrid",       country: "España",    flag: "🇪🇸", node: "ukraine" },
  { code: "AMS", city: "Ámsterdam",    country: "P. Bajos",  flag: "🇳🇱", node: "ukraine" },
  { code: "DFW", city: "Dallas",       country: "EE.UU.",    flag: "🇺🇸", node: "lapaz"   },
  { code: "CAN", city: "Cantón",       country: "China",     flag: "🇨🇳", node: "beijing" },
  { code: "SAO", city: "São Paulo",    country: "Brasil",    flag: "🇧🇷", node: "lapaz"   },
];

const NODE_COLORS = {
  beijing: "bg-red-100 text-red-700",
  ukraine: "bg-blue-100 text-blue-700",
  lapaz:   "bg-green-100 text-green-700",
};
const NODE_LABELS = { beijing: "Pekín", ukraine: "Ucrania", lapaz: "La Paz" };

export default function CitySelector({ value, onChange, placeholder = "Ciudad o aeropuerto" }) {
  const [open,  setOpen]  = useState(false);
  const [query, setQuery] = useState("");
  const ref               = useRef(null);
  const inputRef          = useRef(null);

  const selected = AIRPORTS.find((a) => a.code === value);

  const filtered = query.length === 0
    ? AIRPORTS
    : AIRPORTS.filter((a) =>
        a.code.toLowerCase().includes(query.toLowerCase()) ||
        a.city.toLowerCase().includes(query.toLowerCase()) ||
        a.country.toLowerCase().includes(query.toLowerCase())
      );

  // Cerrar al hacer click fuera
  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const select = (code) => {
    onChange(code);
    setQuery("");
    setOpen(false);
  };

  return (
    <div ref={ref} className="relative w-full">
      {/* Trigger */}
      <button
        type="button"
        onClick={() => { setOpen((o) => !o); setTimeout(() => inputRef.current?.focus(), 50); }}
        className="w-full text-left bg-white border border-gray-200 rounded-xl px-4 py-3 flex items-center gap-2 hover:border-brand-wine transition-colors focus:outline-none focus:border-brand-wine"
      >
        {selected ? (
          <>
            <span className="text-lg">{selected.flag}</span>
            <span className="font-semibold text-gray-900 text-sm">{selected.city}</span>
            <span className="text-xs text-gray-400 ml-0.5">({selected.code})</span>
            <span className={`ml-auto text-xs px-2 py-0.5 rounded-full font-medium ${NODE_COLORS[selected.node]}`}>
              {NODE_LABELS[selected.node]}
            </span>
          </>
        ) : (
          <span className="text-gray-400 text-sm">{placeholder}</span>
        )}
        <svg className={`w-4 h-4 text-gray-400 ml-1 transition-transform ${open ? "rotate-180" : ""} ${selected ? "hidden" : ""}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute z-50 mt-1 w-full bg-white border border-gray-200 rounded-xl shadow-xl overflow-hidden">
          {/* Búsqueda */}
          <div className="p-2 border-b border-gray-100">
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Buscar ciudad o código..."
              className="w-full px-3 py-2 text-sm rounded-lg bg-gray-50 border border-gray-200 focus:outline-none focus:border-brand-wine"
            />
          </div>
          {/* Lista */}
          <ul className="max-h-56 overflow-y-auto">
            {filtered.length === 0 && (
              <li className="px-4 py-3 text-sm text-gray-400 text-center">Sin resultados</li>
            )}
            {filtered.map((a) => (
              <li
                key={a.code}
                onClick={() => select(a.code)}
                className={`px-4 py-2.5 flex items-center gap-3 cursor-pointer hover:bg-gray-50 transition-colors ${
                  value === a.code ? "bg-brand-wine/5" : ""
                }`}
              >
                <span className="text-base">{a.flag}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900">{a.city}
                    <span className="text-gray-400 font-normal ml-1">({a.code})</span>
                  </p>
                  <p className="text-xs text-gray-400">{a.country}</p>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${NODE_COLORS[a.node]}`}>
                  {NODE_LABELS[a.node]}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
