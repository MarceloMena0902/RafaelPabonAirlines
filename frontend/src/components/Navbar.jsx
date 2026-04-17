/**
 * Navbar.jsx — Barra de navegación con selector de idioma dropdown
 */
import { useState, useRef, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import NodeStatus from "./NodeStatus";

const LANGS = [
  { code: "es", label: "Español",    flag: "🇧🇴" },
  { code: "en", label: "English",    flag: "🇺🇸" },
  { code: "fr", label: "Français",   flag: "🇫🇷" },
  { code: "pt", label: "Português",  flag: "🇧🇷" },
  { code: "de", label: "Deutsch",    flag: "🇩🇪" },
  { code: "zh", label: "中文",        flag: "🇨🇳" },
  { code: "uk", label: "Українська", flag: "🇺🇦" },
];

const NAV_LINKS = [
  { to: "/",          key: "nav.home" },
  { to: "/search",    key: "nav.flights" },
  { to: "/flightmap", key: "nav.flightmap", icon: "✈" },
];

export default function Navbar() {
  const { t, i18n }    = useTranslation();
  const location        = useLocation();
  const [open, setOpen] = useState(false);
  const dropRef         = useRef(null);

  const current = LANGS.find(l => l.code === i18n.language) || LANGS[0];

  // Cerrar al hacer click fuera
  useEffect(() => {
    const handler = (e) => {
      if (dropRef.current && !dropRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

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

          {/* ── Selector de idioma (dropdown) ─────────────── */}
          <div ref={dropRef} className="relative">
            <button
              onClick={() => setOpen(o => !o)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-gray-200 text-sm font-medium text-gray-700 hover:border-brand-wine hover:text-brand-wine transition-colors"
            >
              <span>{current.flag}</span>
              <span className="hidden sm:inline">{current.label}</span>
              <span className="text-xs hidden sm:inline">▾</span>
              <span className="sm:hidden text-xs">{current.code.toUpperCase()}</span>
            </button>

            {open && (
              <div className="absolute right-0 mt-1 w-44 bg-white border border-gray-200 rounded-xl shadow-xl overflow-hidden z-50">
                {LANGS.map(l => (
                  <button
                    key={l.code}
                    onClick={() => { i18n.changeLanguage(l.code); setOpen(false); }}
                    className={`w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-left transition-colors ${
                      i18n.language === l.code
                        ? "bg-brand-wine/10 text-brand-wine font-semibold"
                        : "text-gray-700 hover:bg-gray-50"
                    }`}
                  >
                    <span className="text-base">{l.flag}</span>
                    <span>{l.label}</span>
                    {i18n.language === l.code && (
                      <span className="ml-auto text-brand-wine text-xs">✓</span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

        </div>
      </div>
    </nav>
  );
}
