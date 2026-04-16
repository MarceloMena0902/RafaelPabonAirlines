/**
 * CitySelector.jsx
 * Dropdown buscable que consume /nodes/map y /nodes/status.
 * Muestra: bandera + ciudad + IATA + nodo responsable (online/offline).
 */
import { useState, useRef, useEffect } from "react";
import useNodeMap from "../hooks/useNodeMap";

export const AIRPORTS = [
  { code: "ATL", city: "Atlanta",     country: "EE.UU.",   flag: "🇺🇸" },
  { code: "PEK", city: "Pekín",       country: "China",    flag: "🇨🇳" },
  { code: "DXB", city: "Dubái",       country: "EAU",      flag: "🇦🇪" },
  { code: "TYO", city: "Tokio",       country: "Japón",    flag: "🇯🇵" },
  { code: "LON", city: "Londres",     country: "R. Unido", flag: "🇬🇧" },
  { code: "LAX", city: "Los Ángeles", country: "EE.UU.",   flag: "🇺🇸" },
  { code: "PAR", city: "París",       country: "Francia",  flag: "🇫🇷" },
  { code: "FRA", city: "Fráncfort",   country: "Alemania", flag: "🇩🇪" },
  { code: "IST", city: "Estambul",    country: "Turquía",  flag: "🇹🇷" },
  { code: "SIN", city: "Singapur",    country: "Singapur", flag: "🇸🇬" },
  { code: "MAD", city: "Madrid",      country: "España",   flag: "🇪🇸" },
  { code: "AMS", city: "Ámsterdam",   country: "P. Bajos", flag: "🇳🇱" },
  { code: "DFW", city: "Dallas",      country: "EE.UU.",   flag: "🇺🇸" },
  { code: "CAN", city: "Cantón",      country: "China",    flag: "🇨🇳" },
  { code: "SAO", city: "São Paulo",   country: "Brasil",   flag: "🇧🇷" },
];

const NODE_LABELS = { beijing: "Pekín", ukraine: "Ucrania", lapaz: "La Paz" };

function NodeBadge({ node, online }) {
  if (!node) return null;
  const color = online === undefined
    ? "bg-gray-100 text-gray-500"
    : online
      ? "bg-green-100 text-green-700"
      : "bg-red-100 text-red-700";
  return (
    <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${color}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${online ? "bg-green-500" : online === false ? "bg-red-500" : "bg-gray-400"}`} />
      {NODE_LABELS[node] || node}
    </span>
  );
}

export default function CitySelector({ value, onChange, placeholder = "Ciudad o aeropuerto" }) {
  const [open,  setOpen]  = useState(false);
  const [query, setQuery] = useState("");
  const ref               = useRef(null);
  const inputRef          = useRef(null);
  const { nodeMap, nodeStatus } = useNodeMap();

  const selected = AIRPORTS.find((a) => a.code === value);

  const filtered = query.length === 0
    ? AIRPORTS
    : AIRPORTS.filter((a) =>
        a.code.toLowerCase().includes(query.toLowerCase()) ||
        a.city.toLowerCase().includes(query.toLowerCase()) ||
        a.country.toLowerCase().includes(query.toLowerCase())
      );

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const select = (code) => { onChange(code); setQuery(""); setOpen(false); };

  const nodeOf     = (code) => nodeMap[code];
  const onlineOf   = (code) => nodeStatus[nodeMap[code]];

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
            <span className="text-xs text-gray-400">({selected.code})</span>
            <div className="ml-auto">
              <NodeBadge node={nodeOf(selected.code)} online={onlineOf(selected.code)} />
            </div>
          </>
        ) : (
          <>
            <span className="text-gray-400 text-sm flex-1">{placeholder}</span>
            <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute z-50 mt-1 w-full bg-white border border-gray-200 rounded-xl shadow-xl overflow-hidden">
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
          <ul className="max-h-56 overflow-y-auto">
            {filtered.length === 0 && (
              <li className="px-4 py-3 text-sm text-gray-400 text-center">Sin resultados</li>
            )}
            {filtered.map((a) => {
              const node   = nodeOf(a.code);
              const online = onlineOf(a.code);
              return (
                <li
                  key={a.code}
                  onClick={() => select(a.code)}
                  className={`px-4 py-2.5 flex items-center gap-3 cursor-pointer hover:bg-gray-50 transition-colors ${value === a.code ? "bg-brand-wine/5" : ""}`}
                >
                  <span className="text-base">{a.flag}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900">
                      {a.city}
                      <span className="text-gray-400 font-normal ml-1">({a.code})</span>
                    </p>
                    <p className="text-xs text-gray-400">{a.country}</p>
                  </div>
                  <NodeBadge node={node} online={online} />
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
