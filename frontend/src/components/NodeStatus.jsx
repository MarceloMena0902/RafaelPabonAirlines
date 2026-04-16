import { useEffect, useState } from "react";
import { getSystemStatus } from "../api";

const NODE_LABELS = { beijing: "Pekín", ukraine: "Ucrania", lapaz: "La Paz" };

export default function NodeStatus() {
  const [nodes, setNodes] = useState([]);

  useEffect(() => {
    const fetch = () =>
      getSystemStatus()
        .then((s) => setNodes(s.nodes || []))
        .catch(() => {});
    fetch();
    const t = setInterval(fetch, 15000);
    return () => clearInterval(t);
  }, []);

  if (!nodes.length) return null;

  return (
    <div className="flex items-center gap-2">
      {nodes.map((n) => (
        <div key={n.node} className="flex items-center gap-1" title={NODE_LABELS[n.node]}>
          <span className={`w-2 h-2 rounded-full ${n.is_online ? "bg-green-500" : "bg-red-500"}`} />
          <span className="text-xs text-gray-500 hidden lg:inline">{NODE_LABELS[n.node]}</span>
        </div>
      ))}
    </div>
  );
}
