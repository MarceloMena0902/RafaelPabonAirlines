/**
 * SeatMap.jsx — Mapa de cabina realista por modelo de avión
 *
 * Distribuciones reales:
 *   A380-800  → First: 2+2  (3 filas ≈12)   Eco: 3+4+3 (44 filas ≈439)
 *   B777-300ER→ First: 2+2  (3 filas ≈12)   Eco: 3+3+3 (34 filas ≈300)
 *   A350-900  → First: 1+2+1(3 filas =12)   Eco: 3+3+3 (28 filas ≈250)
 *   B787-9    → First: 1+2+1(2 filas = 8)   Eco: 3+3+3 (25 filas ≈220)
 */

// Configuraciones por tipo de aeronave
const CONFIGS = {
  A380: {
    firstGroups: [["A","B"], ["C","D"]],                           // 2-2
    ecoGroups:   [["A","B","C"], ["D","E","F","G"], ["H","J","K"]], // 3-4-3
  },
  B777: {
    firstGroups: [["A","B"], ["C","D"]],                           // 2-2
    ecoGroups:   [["A","B","C"], ["D","E","F"], ["G","H","J"]],    // 3-3-3
  },
  A350: {
    firstGroups: [["A"], ["B","C"], ["D"]],                        // 1-2-1
    ecoGroups:   [["A","B","C"], ["D","E","F"], ["G","H","J"]],    // 3-3-3
  },
  B787: {
    firstGroups: [["A"], ["B","C"], ["D"]],                        // 1-2-1
    ecoGroups:   [["A","B","C"], ["D","E","F"], ["G","H","J"]],    // 3-3-3
  },
};

function getConfig(typeCode) {
  if (!typeCode) return CONFIGS.B777;
  const key = Object.keys(CONFIGS).find(k => typeCode.includes(k));
  return CONFIGS[key] || CONFIGS.B777;
}

function SeatCell({ seatId, isTaken, isSelected, isWrong, onSelect }) {
  let base = "w-7 h-7 rounded-t-lg text-[9px] font-bold border-b-2 flex items-center justify-center transition-all select-none ";

  if (isTaken)    base += "bg-rose-400   border-rose-600   text-white cursor-not-allowed";
  else if (isWrong) base += "bg-gray-100 border-gray-200   text-gray-300 cursor-not-allowed";
  else if (isSelected) base += "bg-brand-wine border-brand-wine2 text-white ring-2 ring-brand-wine ring-offset-1 scale-110 cursor-pointer";
  else              base += "bg-gray-200 border-gray-400   text-gray-600 hover:bg-amber-200 hover:border-amber-500 hover:text-gray-900 cursor-pointer";

  return (
    <button
      type="button"
      disabled={isTaken || isWrong}
      onClick={() => !isTaken && !isWrong && onSelect(seatId)}
      className={base}
      title={seatId}
    >
      {seatId.replace(/\d+/g, "")}
    </button>
  );
}

export default function SeatMap({ aircraft, takenSeats = [], selectedSeat, cabinClass, onSelect }) {
  if (!aircraft) return null;

  const cfg = getConfig(aircraft.type_code);

  const seatsPerFirstRow = cfg.firstGroups.reduce((a, g) => a + g.length, 0);
  const seatsPerEcoRow   = cfg.ecoGroups.reduce((a, g) => a + g.length, 0);
  const firstRows = Math.ceil((aircraft.first_class_seats || 0) / seatsPerFirstRow);
  const ecoRows   = Math.ceil((aircraft.economy_seats    || 0) / seatsPerEcoRow);

  const renderRow = (rowNum, groups, isFirst) => {
    const wrongCabin = isFirst ? cabinClass !== "FIRST" : cabinClass !== "ECONOMY";
    return (
      <div key={rowNum} className="flex items-center gap-1">
        {/* Número de fila izquierdo */}
        <span className="text-[9px] text-gray-400 w-5 text-right shrink-0">{rowNum}</span>

        {/* Grupos de asientos */}
        <div className="flex gap-3">
          {groups.map((group, gi) => (
            <div key={gi} className="flex gap-0.5">
              {group.map((col) => {
                const seatId = `${rowNum}${col}`;
                return (
                  <SeatCell
                    key={seatId}
                    seatId={seatId}
                    isTaken={takenSeats.includes(seatId)}
                    isSelected={selectedSeat === seatId}
                    isWrong={wrongCabin}
                    onSelect={onSelect}
                  />
                );
              })}
            </div>
          ))}
        </div>

        {/* Número de fila derecho */}
        <span className="text-[9px] text-gray-400 w-5 text-left shrink-0">{rowNum}</span>
      </div>
    );
  };

  return (
    <div className="font-mono">
      {/* Leyenda */}
      <div className="flex gap-3 text-[10px] text-gray-500 mb-3 flex-wrap">
        <span className="flex items-center gap-1">
          <span className="w-4 h-4 rounded-t-md bg-amber-200 border-b-2 border-amber-500 inline-block" /> Disponible
        </span>
        <span className="flex items-center gap-1">
          <span className="w-4 h-4 rounded-t-md bg-rose-400 border-b-2 border-rose-600 inline-block" /> Ocupado
        </span>
        <span className="flex items-center gap-1">
          <span className="w-4 h-4 rounded-t-md bg-brand-wine border-b-2 border-brand-wine2 inline-block" /> Seleccionado
        </span>
      </div>

      {/* Morro del avión */}
      <div className="flex justify-center mb-1">
        <div className="w-8 h-4 border-t-2 border-x-2 border-gray-300 rounded-t-full bg-gray-100" />
      </div>

      {/* Scroll de cabina */}
      <div className="overflow-y-auto max-h-96 rounded-xl border border-gray-200 bg-gray-50 p-3 space-y-0.5">

        {/* ── Primera Clase ──────────────────────────────────── */}
        <div className="text-[9px] font-bold text-amber-700 text-center mb-1 bg-amber-50 rounded py-0.5">
          ★ PRIMERA CLASE — {aircraft.type_code}
        </div>
        {Array.from({ length: firstRows }, (_, i) => i + 1).map((row) =>
          renderRow(row, cfg.firstGroups, true)
        )}

        {/* ── Separador cabina ───────────────────────────────── */}
        <div className="flex items-center gap-1 py-1">
          <div className="flex-1 border-t-2 border-dashed border-brand-wine/40" />
          <span className="text-[9px] text-brand-wine/70 font-medium px-1">ECONÓMICA</span>
          <div className="flex-1 border-t-2 border-dashed border-brand-wine/40" />
        </div>

        {/* ── Economía ───────────────────────────────────────── */}
        {Array.from({ length: ecoRows }, (_, i) => firstRows + i + 1).map((row) =>
          renderRow(row, cfg.ecoGroups, false)
        )}
      </div>

      {/* Cola del avión */}
      <div className="flex justify-center mt-1">
        <div className="w-12 h-3 border-b-2 border-x-2 border-gray-300 rounded-b-full bg-gray-100" />
      </div>
    </div>
  );
}
