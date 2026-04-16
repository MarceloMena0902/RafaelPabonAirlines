/**
 * useNodeMap.js
 * Combina /nodes/map  (aeropuerto → nodo)
 *     con /nodes/status (nodo → online/offline)
 * y los expone listos para usar en cualquier componente.
 */
import { useEffect, useState } from "react";
import { getNodeMap, getSystemStatus } from "../api";

export default function useNodeMap() {
  const [nodeMap,    setNodeMap]    = useState({});   // { PEK: "beijing", ... }
  const [nodeStatus, setNodeStatus] = useState({});   // { beijing: true, ... }
  const [loading,    setLoading]    = useState(true);

  const refresh = () =>
    Promise.all([getNodeMap(), getSystemStatus()])
      .then(([map, status]) => {
        setNodeMap(map);
        const statusMap = {};
        (status.nodes || []).forEach((n) => { statusMap[n.node] = n.is_online; });
        setNodeStatus(statusMap);
      })
      .catch(() => {})
      .finally(() => setLoading(false));

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 15000);
    return () => clearInterval(t);
  }, []);

  return { nodeMap, nodeStatus, loading };
}
