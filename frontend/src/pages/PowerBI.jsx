/**
 * PowerBI.jsx — Dashboard gerencial con datos reales del sistema
 * Reemplaza el iframe de Power BI con métricas en vivo.
 */
import { useEffect, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { getAnalyticsSummary } from "../api";

// ── Colores por nodo ──────────────────────────────────────────
const NODE_COLOR = {
  beijing: { bg: "bg-red-500",   light: "bg-red-50",  text: "text-red-700",  border: "border-red-200" },
  ukraine: { bg: "bg-blue-500",  light: "bg-blue-50", text: "text-blue-700", border: "border-blue-200" },
  lapaz:   { bg: "bg-green-500", light: "bg-green-50",text: "text-green-700",border: "border-green-200" },
};
const NODE_LABEL = { beijing: "Beijing", ukraine: "Ucrania", lapaz: "La Paz" };

// ── Mini barra horizontal ─────────────────────────────────────
function Bar({ value, max, color = "bg-brand-wine" }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all duration-700`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-500 w-8 text-right">{pct}%</span>
    </div>
  );
}

// ── Tarjeta KPI ───────────────────────────────────────────────
function KpiCard({ label, value, sub, color = "text-gray-900", icon }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 flex flex-col gap-1">
      <div className="flex items-center gap-2 text-gray-400 text-xs uppercase tracking-wider mb-1">
        {icon && <span className="text-base">{icon}</span>}
        {label}
      </div>
      <div className={`text-3xl font-bold ${color}`}>{value}</div>
      {sub && <div className="text-xs text-gray-400">{sub}</div>}
    </div>
  );
}

// ── Indicador de nodo online ──────────────────────────────────
function NodeBadge({ name, online }) {
  const c = NODE_COLOR[name] || {};
  return (
    <div className={`flex items-center gap-2 rounded-xl border px-3 py-2 ${c.light || "bg-gray-50"} ${c.border || "border-gray-200"}`}>
      <span className={`w-2.5 h-2.5 rounded-full ${online ? c.bg : "bg-gray-300"}`} />
      <span className={`text-sm font-medium ${online ? c.text : "text-gray-400"}`}>
        {NODE_LABEL[name] || name}
      </span>
      <span className={`text-xs ml-auto ${online ? "text-green-600" : "text-gray-400"}`}>
        {online ? "Online" : "Offline"}
      </span>
    </div>
  );
}

// ── Gráfico de barras verticales simple ───────────────────────
function BarChart({ data, colorFn }) {
  if (!data || data.length === 0) return <p className="text-xs text-gray-400 text-center py-4">Sin datos</p>;
  const max = Math.max(...data.map(d => d.value), 1);
  return (
    <div className="flex items-end gap-2 h-28 mt-2">
      {data.map((d, i) => {
        const h = Math.max(4, Math.round((d.value / max) * 96));
        const color = colorFn ? colorFn(i) : "bg-brand-wine";
        return (
          <div key={i} className="flex flex-col items-center flex-1 min-w-0 gap-1">
            <span className="text-[10px] text-gray-500 font-medium">{d.value}</span>
            <div className={`w-full rounded-t-md ${color} transition-all duration-700`} style={{ height: `${h}px` }} />
            <span className="text-[9px] text-gray-400 truncate w-full text-center leading-tight">{d.label}</span>
          </div>
        );
      })}
    </div>
  );
}

// ── Componente principal ──────────────────────────────────────
export default function Dashboard() {
  const { t } = useTranslation();
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(false);
  const [lastUpd, setLastUpd] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(false);
    getAnalyticsSummary()
      .then(d => { setData(d); setLastUpd(new Date()); })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 30_000);
    return () => clearInterval(interval);
  }, [load]);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-100 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-brand-wine flex items-center justify-center text-white font-bold text-sm">
            RP
          </div>
          <div>
            <h1 className="font-bold text-gray-900 text-base">
              {t("dashboard.title") || "Dashboard Gerencial"}
            </h1>
            <p className="text-gray-400 text-xs">
              {t("dashboard.subtitle") || "RafaelPabón Airlines — Métricas en tiempo real"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {lastUpd && (
            <span className="text-xs text-gray-400">
              {t("dashboard.updated") || "Actualizado"}: {lastUpd.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={load}
            disabled={loading}
            className="bg-brand-wine text-white text-xs font-semibold px-4 py-2 rounded-xl
                       hover:bg-brand-wine2 disabled:opacity-50 transition-colors"
          >
            {loading ? "..." : (t("dashboard.refresh") || "Actualizar")}
          </button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-700 text-sm text-center mb-6">
            {t("dashboard.error") || "Error al cargar datos. Verifica que el backend esté activo."}
          </div>
        )}

        {loading && !data && (
          <div className="flex justify-center py-24">
            <div className="w-10 h-10 border-4 border-brand-wine border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {data && (
          <>
            {/* ── Nodos ─────────────────────────────────────────────── */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6">
              {Object.entries(data.nodes_online || {}).map(([name, online]) => (
                <NodeBadge key={name} name={name} online={online} />
              ))}
            </div>

            {/* ── KPIs principales ──────────────────────────────────── */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <KpiCard
                icon="✈"
                label={t("dashboard.confirmed") || "Confirmadas"}
                value={data.total_confirmed}
                color="text-green-600"
                sub={t("dashboard.tickets_sold") || "boletos vendidos"}
              />
              <KpiCard
                icon="⏳"
                label={t("dashboard.reserved") || "Reservadas"}
                value={data.total_reserved}
                color="text-amber-600"
                sub={t("dashboard.pending_payment") || "pago pendiente"}
              />
              <KpiCard
                icon="💵"
                label={t("dashboard.revenue") || "Ingresos"}
                value={`$${(data.revenue_total || 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
                color="text-brand-wine"
                sub="USD confirmado"
              />
              <KpiCard
                icon="🛫"
                label={t("dashboard.total_flights") || "Vuelos"}
                value={data.occupancy?.total_flights ?? 0}
                sub={t("dashboard.in_system") || "en el sistema"}
              />
            </div>

            {/* ── Fila secundaria ────────────────────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">

              {/* Ingresos por nodo */}
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
                <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wider mb-3">
                  {t("dashboard.revenue_by_node") || "Ingresos por nodo"}
                </h3>
                {Object.entries(data.revenue_by_node || {}).length === 0
                  ? <p className="text-xs text-gray-400 text-center py-4">Sin datos</p>
                  : <div className="space-y-3">
                    {Object.entries(data.revenue_by_node).map(([node, rev]) => {
                      const total = data.revenue_total || 1;
                      const c = NODE_COLOR[node];
                      return (
                        <div key={node}>
                          <div className="flex justify-between text-xs mb-1">
                            <span className={`font-medium ${c?.text || "text-gray-700"}`}>
                              {NODE_LABEL[node] || node}
                            </span>
                            <span className="text-gray-600">
                              ${(rev || 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}
                            </span>
                          </div>
                          <Bar value={rev} max={total} color={c?.bg || "bg-brand-wine"} />
                        </div>
                      );
                    })}
                  </div>
                }
              </div>

              {/* Reservas por clase */}
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
                <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wider mb-3">
                  {t("dashboard.by_cabin") || "Por clase de cabina"}
                </h3>
                <BarChart
                  data={Object.entries(data.by_cabin || {}).map(([k, v]) => ({
                    label: k === "ECONOMY" ? "Económica" : "Primera",
                    value: v,
                  }))}
                  colorFn={i => i === 0 ? "bg-blue-400" : "bg-amber-400"}
                />
              </div>

              {/* Ocupación */}
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
                <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wider mb-3">
                  {t("dashboard.occupancy") || "Ocupación promedio"}
                </h3>
                <div className="space-y-4 mt-2">
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-gray-600">Económica</span>
                      <span className="font-semibold text-gray-800">{data.occupancy?.economy ?? 0}%</span>
                    </div>
                    <Bar value={data.occupancy?.economy ?? 0} max={100} color="bg-blue-400" />
                  </div>
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-gray-600">Primera clase</span>
                      <span className="font-semibold text-gray-800">{data.occupancy?.first_class ?? 0}%</span>
                    </div>
                    <Bar value={data.occupancy?.first_class ?? 0} max={100} color="bg-amber-400" />
                  </div>
                </div>
              </div>
            </div>

            {/* ── Rutas más vendidas ─────────────────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
                <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wider mb-4">
                  {t("dashboard.top_routes") || "Top rutas más vendidas"}
                </h3>
                {(!data.top_routes || data.top_routes.length === 0) ? (
                  <p className="text-xs text-gray-400 text-center py-4">Sin datos de rutas</p>
                ) : (
                  <div className="space-y-3">
                    {data.top_routes.map((r, i) => (
                      <div key={i} className="flex items-center gap-3">
                        <span className="w-5 h-5 rounded-full bg-brand-wine text-white text-[10px] font-bold flex items-center justify-center shrink-0">
                          {i + 1}
                        </span>
                        <span className="text-sm font-semibold text-gray-800 flex-1">{r.route}</span>
                        <span className="text-xs text-gray-500">{r.count} reservas</span>
                        <Bar
                          value={r.count}
                          max={data.top_routes[0]?.count || 1}
                          color="bg-brand-wine"
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Reservas por nodo origen */}
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
                <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wider mb-4">
                  {t("dashboard.by_node") || "Reservas por nodo de compra"}
                </h3>
                <BarChart
                  data={Object.entries(data.by_node || {}).map(([k, v]) => ({
                    label: NODE_LABEL[k] || k,
                    value: v,
                  }))}
                  colorFn={i => {
                    const nodes = Object.keys(data.by_node || {});
                    const name  = nodes[i];
                    return NODE_COLOR[name]?.bg || "bg-gray-400";
                  }}
                />
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
