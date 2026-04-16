const COLS = ["A", "B", "C", "D", "E", "F"];

export default function SeatMap({ aircraft, takenSeats = [], selectedSeat, cabinClass, onSelect }) {
  if (!aircraft) return null;

  const firstRows   = Math.ceil(aircraft.first_class_seats / 4);
  const economyRows = Math.ceil(aircraft.economy_seats / 6);

  const renderSeat = (row, col, isFirst) => {
    const seatId = `${row}${col}`;
    const isTaken    = takenSeats.includes(seatId);
    const isSelected = selectedSeat === seatId;
    const wrongCabin = isFirst ? cabinClass !== "FIRST" : cabinClass !== "ECONOMY";

    let cls = "w-7 h-7 rounded text-xs font-medium border transition-colors ";
    if (isTaken)         cls += "bg-gray-300 border-gray-300 text-gray-400 cursor-not-allowed";
    else if (isSelected) cls += "bg-brand-wine border-brand-wine text-white";
    else if (wrongCabin) cls += "bg-gray-100 border-gray-200 text-gray-300 cursor-not-allowed";
    else                 cls += "bg-white border-gray-300 hover:border-brand-wine hover:bg-brand-wine/10 cursor-pointer";

    return (
      <button
        key={seatId}
        type="button"
        disabled={isTaken || wrongCabin}
        onClick={() => onSelect(seatId)}
        className={cls}
        title={seatId}
      >
        {col}
      </button>
    );
  };

  return (
    <div className="overflow-y-auto max-h-80 space-y-1 p-2 bg-gray-50 rounded-xl border border-gray-200">
      {/* Primera clase */}
      {Array.from({ length: firstRows }, (_, i) => i + 1).map((row) => (
        <div key={`f${row}`} className="flex gap-1 items-center justify-center">
          <span className="text-xs text-gray-400 w-5 text-right">{row}</span>
          <div className="flex gap-1">
            {["A","B"].map((c) => renderSeat(row, c, true))}
          </div>
          <div className="w-3" />
          <div className="flex gap-1">
            {["C","D"].map((c) => renderSeat(row, c, true))}
          </div>
        </div>
      ))}
      {/* Separador */}
      <div className="border-t-2 border-dashed border-brand-wine/30 my-1" />
      {/* Económica */}
      {Array.from({ length: economyRows }, (_, i) => i + firstRows + 1).map((row) => (
        <div key={`e${row}`} className="flex gap-1 items-center justify-center">
          <span className="text-xs text-gray-400 w-5 text-right">{row}</span>
          <div className="flex gap-1">
            {["A","B","C"].map((c) => renderSeat(row, c, false))}
          </div>
          <div className="w-3" />
          <div className="flex gap-1">
            {["D","E","F"].map((c) => renderSeat(row, c, false))}
          </div>
        </div>
      ))}
    </div>
  );
}
