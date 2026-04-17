/**
 * SeatMap.jsx — Mapa de cabina con estados de asiento
 *
 * Colores por estado:
 *   Libre     → azul
 *   RESERVED  → amarillo/dorado
 *   CONFIRMED → verde
 *   (cabina incorrecta) → gris claro
 *
 * Al hacer clic en cualquier asiento aparece un popup con:
 *   - Número de asiento y estado
 *   - Datos del pasajero (solo lectura si está ocupado)
 *   - Campo de pasaporte + nombre (editable si está libre)
 *   - Botones Comprar / Reservar según estado
 *
 * Props:
 *   aircraft      { type_code, first_class_seats, economy_seats }
 *   seatMap       { [seatId]: { status, passenger_passport, passenger_name, transaction_id } }
 *   cabinClass    'ECONOMY' | 'FIRST'
 *   onBuy(seatId, passport, name)
 *   onReserve(seatId, passport, name)
 *   lookupPassport(passport) → Promise<{ full_name } | null>
 */
import { useEffect, useRef, useState } from "react";

// ── Configuraciones por tipo de aeronave ──────────────────────
const CONFIGS = {
  A380: {
    firstGroups: [["A","B"], ["C","D"]],
    ecoGroups:   [["A","B","C"], ["D","E","F","G"], ["H","J","K"]],
  },
  B777: {
    firstGroups: [["A","B"], ["C","D"]],
    ecoGroups:   [["A","B","C"], ["D","E","F"], ["G","H","J"]],
  },
  A350: {
    firstGroups: [["A"], ["B","C"], ["D"]],
    ecoGroups:   [["A","B","C"], ["D","E","F"], ["G","H","J"]],
  },
  B787: {
    firstGroups: [["A"], ["B","C"], ["D"]],
    ecoGroups:   [["A","B","C"], ["D","E","F"], ["G","H","J"]],
  },
};

function getConfig(typeCode) {
  if (!typeCode) return CONFIGS.B777;
  const key = Object.keys(CONFIGS).find(k => typeCode.includes(k));
  return CONFIGS[key] || CONFIGS.B777;
}

// ── Clases de color por estado ────────────────────────────────
function seatClasses(status, isSelected, isWrongCabin) {
  const base = "w-7 h-7 rounded-t-lg text-[9px] font-bold border-b-2 flex items-center justify-center transition-all select-none ";
  if (isWrongCabin)
    return base + "bg-gray-100 border-gray-200 text-gray-300 cursor-not-allowed";
  if (isSelected)
    return base + "bg-brand-wine border-brand-wine2 text-white ring-2 ring-brand-wine ring-offset-1 scale-110 cursor-pointer";
  if (status === "CONFIRMED")
    return base + "bg-green-500 border-green-700 text-white cursor-pointer hover:bg-green-600";
  if (status === "RESERVED")
    return base + "bg-amber-400 border-amber-600 text-white cursor-pointer hover:bg-amber-500";
  // Libre
  return base + "bg-blue-200 border-blue-400 text-blue-700 hover:bg-blue-300 hover:border-blue-500 cursor-pointer";
}

// ── Popup de asiento ──────────────────────────────────────────
function SeatPopup({ seatId, info, cabinClass, onClose, onBuy, onReserve, lookupPassport }) {
  const [passport,  setPassport]  = useState(info?.passenger_passport || "");
  const [paxName,   setPaxName]   = useState(info?.passenger_name     || "");
  const [looking,   setLooking]   = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const debounceRef = useRef(null);

  const isOccupied = !!info;
  const status     = info?.status || "LIBRE";

  const statusLabel = {
    CONFIRMED: "Vendido",
    RESERVED:  "Reservado",
    LIBRE:     "Libre",
  }[status] || status;

  const statusColor = {
    CONFIRMED: "bg-green-100 text-green-700",
    RESERVED:  "bg-amber-100 text-amber-700",
    LIBRE:     "bg-blue-100 text-blue-700",
  }[status] || "bg-gray-100 text-gray-700";

  // Autocompletar nombre al escribir pasaporte
  useEffect(() => {
    if (isOccupied) return;
    clearTimeout(debounceRef.current);
    if (passport.trim().length < 4) { setPaxName(""); return; }
    debounceRef.current = setTimeout(async () => {
      setLooking(true);
      try {
        const found = await lookupPassport(passport.trim().toUpperCase());
        if (found) setPaxName(found.full_name);
        else        setPaxName("");
      } catch {
        setPaxName("");
      } finally {
        setLooking(false);
      }
    }, 400);
    return () => clearTimeout(debounceRef.current);
  }, [passport, isOccupied, lookupPassport]);

  const handleAction = async (action) => {
    setSubmitting(true);
    try {
      if (action === "buy")    await onBuy(seatId, passport.trim().toUpperCase(), paxName.trim());
      if (action === "reserve") await onReserve(seatId, passport.trim().toUpperCase(), paxName.trim());
    } finally {
      setSubmitting(false);
    }
  };

  const canAct = !isOccupied && passport.trim().length >= 4;

  return (
    <div className="absolute z-50 bg-white border-2 border-gray-300 rounded-xl shadow-2xl p-4 w-64"
         style={{ top: "50%", left: "50%", transform: "translate(-50%, -50%)" }}>

      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <span className="font-bold text-gray-800 text-sm">Asiento: <span className="text-brand-wine">{seatId}</span></span>
        <button onClick={onClose}
          className="text-gray-400 hover:text-gray-700 text-lg leading-none font-bold">×</button>
      </div>

      {/* Estado */}
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs text-gray-500">Estado:</span>
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${statusColor}`}>
          {statusLabel}
        </span>
        <span className="text-xs text-gray-400">{cabinClass === "FIRST" ? "1ª Clase" : "Económica"}</span>
      </div>

      {/* Pasaporte */}
      <div className="mb-2">
        <label className="text-xs text-gray-500 block mb-1">Pasaporte:</label>
        {isOccupied ? (
          <div className="font-mono text-sm text-gray-700 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
            {info.passenger_passport}
          </div>
        ) : (
          <input
            type="text"
            value={passport}
            onChange={e => setPassport(e.target.value)}
            placeholder="Ej: LT12345678"
            className="w-full font-mono text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:border-brand-wine"
          />
        )}
      </div>

      {/* Nombre pasajero */}
      <div className="mb-4">
        <label className="text-xs text-gray-500 block mb-1">
          Pasajero:{looking && <span className="text-gray-400 ml-1">(buscando...)</span>}
        </label>
        {isOccupied ? (
          <div className="text-sm text-gray-700 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
            {info.passenger_name || <span className="text-gray-400 italic">Sin nombre registrado</span>}
          </div>
        ) : (
          <input
            type="text"
            value={paxName}
            onChange={e => setPaxName(e.target.value)}
            placeholder="Nombre completo"
            className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:border-brand-wine"
          />
        )}
      </div>

      {/* Acciones */}
      {!isOccupied && (
        <div className="flex gap-2">
          <button
            disabled={!canAct || submitting}
            onClick={() => handleAction("buy")}
            className="flex-1 bg-green-600 text-white text-sm font-semibold py-2 rounded-lg hover:bg-green-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Comprar
          </button>
          <button
            disabled={!canAct || submitting}
            onClick={() => handleAction("reserve")}
            className="flex-1 bg-amber-500 text-white text-sm font-semibold py-2 rounded-lg hover:bg-amber-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Reservar
          </button>
        </div>
      )}

      {isOccupied && status === "RESERVED" && (
        <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-center">
          Reservado — pendiente de compra
        </p>
      )}
      {isOccupied && status === "CONFIRMED" && (
        <p className="text-xs text-green-600 bg-green-50 border border-green-200 rounded-lg px-3 py-2 text-center">
          Asiento vendido
        </p>
      )}

      {!canAct && !isOccupied && (
        <p className="text-xs text-gray-400 mt-2 text-center">
          Ingresa el pasaporte para continuar
        </p>
      )}
    </div>
  );
}

// ── Celda de asiento ──────────────────────────────────────────
function SeatCell({ seatId, status, isSelected, isWrongCabin, onClick }) {
  return (
    <button
      type="button"
      disabled={isWrongCabin}
      onClick={() => !isWrongCabin && onClick(seatId)}
      className={seatClasses(status, isSelected, isWrongCabin)}
      title={seatId}
    >
      {seatId.replace(/\d+/g, "")}
    </button>
  );
}

// ── Componente principal ──────────────────────────────────────
export default function SeatMap({
  aircraft,
  seatMap = {},       // { [seatId]: { status, passenger_passport, passenger_name } }
  cabinClass,
  onBuy,
  onReserve,
  lookupPassport,
}) {
  const [popup, setPopup] = useState(null); // seatId | null

  if (!aircraft) return null;

  const cfg = getConfig(aircraft.type_code);
  const seatsPerFirstRow = cfg.firstGroups.reduce((a, g) => a + g.length, 0);
  const seatsPerEcoRow   = cfg.ecoGroups.reduce((a, g)   => a + g.length, 0);
  const firstRows = Math.ceil((aircraft.first_class_seats || 0) / seatsPerFirstRow);
  const ecoRows   = Math.ceil((aircraft.economy_seats    || 0) / seatsPerEcoRow);

  const handleSeatClick = (seatId) => {
    setPopup(prev => prev === seatId ? null : seatId);
  };

  const renderRow = (rowNum, groups, isFirst) => {
    const wrongCabin = isFirst ? cabinClass !== "FIRST" : cabinClass !== "ECONOMY";
    return (
      <div key={rowNum} className="flex items-center gap-1">
        <span className="text-[9px] text-gray-400 w-5 text-right shrink-0">{rowNum}</span>
        <div className="flex gap-3">
          {groups.map((group, gi) => (
            <div key={gi} className="flex gap-0.5">
              {group.map((col) => {
                const seatId = `${rowNum}${col}`;
                const info   = seatMap[seatId];
                return (
                  <SeatCell
                    key={seatId}
                    seatId={seatId}
                    status={info?.status || null}
                    isSelected={popup === seatId}
                    isWrongCabin={wrongCabin}
                    onClick={handleSeatClick}
                  />
                );
              })}
            </div>
          ))}
        </div>
        <span className="text-[9px] text-gray-400 w-5 text-left shrink-0">{rowNum}</span>
      </div>
    );
  };

  return (
    <div className="font-mono relative">

      {/* Leyenda */}
      <div className="flex gap-3 text-[10px] text-gray-500 mb-3 flex-wrap">
        <span className="flex items-center gap-1">
          <span className="w-4 h-4 rounded-t-md bg-blue-200 border-b-2 border-blue-400 inline-block" />
          Libre
        </span>
        <span className="flex items-center gap-1">
          <span className="w-4 h-4 rounded-t-md bg-amber-400 border-b-2 border-amber-600 inline-block" />
          Reservado
        </span>
        <span className="flex items-center gap-1">
          <span className="w-4 h-4 rounded-t-md bg-green-500 border-b-2 border-green-700 inline-block" />
          Vendido
        </span>
        <span className="flex items-center gap-1">
          <span className="w-4 h-4 rounded-t-md bg-brand-wine border-b-2 border-brand-wine2 inline-block" />
          Seleccionado
        </span>
      </div>

      {/* Morro del avión */}
      <div className="flex justify-center mb-1">
        <div className="w-8 h-4 border-t-2 border-x-2 border-gray-300 rounded-t-full bg-gray-100" />
      </div>

      {/* Scroll de cabina */}
      <div className="overflow-y-auto max-h-96 rounded-xl border border-gray-200 bg-gray-50 p-3 space-y-0.5">

        {/* Primera Clase */}
        <div className="text-[9px] font-bold text-amber-700 text-center mb-1 bg-amber-50 rounded py-0.5">
          ★ PRIMERA CLASE — {aircraft.type_code}
        </div>
        {Array.from({ length: firstRows }, (_, i) => i + 1).map(row =>
          renderRow(row, cfg.firstGroups, true)
        )}

        {/* Separador */}
        <div className="flex items-center gap-1 py-1">
          <div className="flex-1 border-t-2 border-dashed border-brand-wine/40" />
          <span className="text-[9px] text-brand-wine/70 font-medium px-1">ECONÓMICA</span>
          <div className="flex-1 border-t-2 border-dashed border-brand-wine/40" />
        </div>

        {/* Económica */}
        {Array.from({ length: ecoRows }, (_, i) => firstRows + i + 1).map(row =>
          renderRow(row, cfg.ecoGroups, false)
        )}
      </div>

      {/* Cola del avión */}
      <div className="flex justify-center mt-1">
        <div className="w-12 h-3 border-b-2 border-x-2 border-gray-300 rounded-b-full bg-gray-100" />
      </div>

      {/* Popup de asiento */}
      {popup && (
        <>
          <div className="absolute inset-0 bg-black/20 rounded-xl z-40"
               onClick={() => setPopup(null)} />
          <SeatPopup
            seatId={popup}
            info={seatMap[popup] || null}
            cabinClass={cabinClass}
            onClose={() => setPopup(null)}
            onBuy={async (seatId, passport, name) => {
              await onBuy(seatId, passport, name);
              setPopup(null);
            }}
            onReserve={async (seatId, passport, name) => {
              await onReserve(seatId, passport, name);
              setPopup(null);
            }}
            lookupPassport={lookupPassport}
          />
        </>
      )}
    </div>
  );
}
