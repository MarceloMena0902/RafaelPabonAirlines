/**
 * Navbar.jsx
 * ──────────
 * Barra de navegación estilo Qatar Airways:
 *   • Fondo blanco, sombra sutil
 *   • Logo RPA a la izquierda
 *   • Links de navegación centrados
 *   • NodeStatus dots + selector de idioma a la derecha
 */
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import NodeStatus from "./NodeStatus";

const LANGS = [
  { code: "es", label: "ES" },
  { code: "en", label: "EN" },
  { code: "zh", label: "中文" },
  { code: "uk", label: "УК" },
];

const NAV_LINKS = [
  { to: "/",       key: "nav.home" },
  { to: "/search", key: "nav.flights" },
];

export default function Navbar() {
  const { t, i18n } = useTranslation();
  const location    = useLocation();

  return (
    <nav className="bg-white shadow-sm border-b border-gray-100 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex items-center h-16 gap-6">

          {/* ── Logo ──────────────────────────────────────── */}
          <Link to="/" className="flex items-center gap-3 shrink-0">
            <img
              src="/logo.png"
              alt="RafaelPabón Airlines"
              className="h-10 w-auto object-contain"
              onError={(e) => {
                e.currentTarget.style.display = "none";
                e.currentTarget.nextSibling.style.display = "flex";
              }}
            />
            {/* Fallback texto si no carga la imagen */}
            <div
              className="hidden w-10 h-10 bg-brand-wine rounded-full items-center justify-center font-bold text-white text-xs"
              aria-hidden
            >
              RPA
            </div>
            <span className="font-bold text-brand-wine text-base hidden md:inline tracking-tight">
              RafaelPabón Airlines
            </span>
          </Link>

          {/* ── Links de navegación ───────────────────────── */}
          <div className="flex gap-1 flex-1">
            {NAV_LINKS.map(({ to, key }) => {
              const active = location.pathname === to;
              return (
                <Link
                  key={to}
                  to={to}
                  className={`px-4 py-2 text-sm font-medium rounded-full transition-colors ${
                    active
                      ? "bg-brand-wine/10 text-brand-wine"
                      : "text-gray-600 hover:text-brand-wine hover:bg-gray-50"
                  }`}
                >
                  {t(key)}
                </Link>
              );
            })}
          </div>

          {/* ── Estado de nodos ───────────────────────────── */}
          <NodeStatus />

          {/* ── Selector de idioma ────────────────────────── */}
          <div className="flex gap-0.5 text-xs">
            {LANGS.map((l) => (
              <button
                key={l.code}
                onClick={() => i18n.changeLanguage(l.code)}
                className={`px-2.5 py-1.5 rounded-full transition-colors font-medium ${
                  i18n.language === l.code
                    ? "bg-brand-wine text-white"
                    : "text-gray-500 hover:text-brand-wine hover:bg-gray-100"
                }`}
              >
                {l.label}
              </button>
            ))}
          </div>

        </div>
      </div>
    </nav>
  );
}
