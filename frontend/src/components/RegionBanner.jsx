export default function RegionBanner({ systemStatus }) {
  if (!systemStatus) return null;
  const blocked = systemStatus.all_blocked_airports || [];
  const offlineNodes = (systemStatus.nodes || []).filter((n) => !n.is_online);
  if (!offlineNodes.length) return null;

  return (
    <div className="bg-red-600 text-white text-sm text-center py-2 px-4">
      ⚠️ Nodo(s) caído(s):{" "}
      <strong>{offlineNodes.map((n) => n.node).join(", ")}</strong>.
      Aeropuertos bloqueados: <strong>{blocked.join(", ") || "ninguno"}</strong>.
      Las ventas para estas rutas están suspendidas.
    </div>
  );
}
