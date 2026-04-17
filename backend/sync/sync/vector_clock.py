"""
sync/vector_clock.py
────────────────────
Implementación de Relojes Vectoriales para garantizar consistencia
causal en operaciones concurrentes entre los 3 nodos.

Reglas:
  • Evento local en nodo X    → vc[X] += 1
  • Enviar mensaje desde X    → adjuntar vc actual
  • Recibir mensaje en Y de X → vc[k] = max(local[k], recv[k])  ∀k
                                 luego vc[Y] += 1
  • VC1 < VC2                 → VC1[k] ≤ VC2[k] ∀k y ∃k: VC1[k] < VC2[k]
  • VC1 || VC2 (concurrentes) → ninguno domina al otro → conflicto
"""
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar


class VCRelation(str, Enum):
    BEFORE     = "BEFORE"      # VC1 < VC2 (causal)
    AFTER      = "AFTER"       # VC1 > VC2 (causal)
    EQUAL      = "EQUAL"       # idénticos
    CONCURRENT = "CONCURRENT"  # conflicto, requiere resolución


NODES: list[str] = ["beijing", "ukraine", "lapaz"]


@dataclass
class VectorClock:
    """
    Reloj vectorial con 3 dimensiones (una por nodo).
    Inmutable externamente; usar tick() y merge() para avanzarlo.
    """
    _clocks: ClassVar[list[str]] = NODES
    beijing: int = 0
    ukraine: int = 0
    lapaz:   int = 0

    # ── Operaciones de avance ─────────────────────────────────

    def tick(self, node: str) -> "VectorClock":
        """Retorna un nuevo VC con el contador del nodo dado incrementado."""
        values = self.to_dict()
        values[node] += 1
        return VectorClock(**values)

    def merge(self, other: "VectorClock", local_node: str) -> "VectorClock":
        """
        Al recibir un mensaje: toma el máximo elemento a elemento
        y luego hace tick del nodo local.
        """
        merged = VectorClock(
            beijing=max(self.beijing, other.beijing),
            ukraine=max(self.ukraine, other.ukraine),
            lapaz  =max(self.lapaz,   other.lapaz),
        )
        return merged.tick(local_node)

    # ── Comparación ──────────────────────────────────────────

    def compare(self, other: "VectorClock") -> VCRelation:
        """Determina la relación causal entre self y other."""
        self_leq  = (self.beijing  <= other.beijing  and
                     self.ukraine  <= other.ukraine   and
                     self.lapaz    <= other.lapaz)
        other_leq = (other.beijing <= self.beijing   and
                     other.ukraine <= self.ukraine    and
                     other.lapaz   <= self.lapaz)

        if self == other:
            return VCRelation.EQUAL
        if self_leq:
            return VCRelation.BEFORE
        if other_leq:
            return VCRelation.AFTER
        return VCRelation.CONCURRENT

    def dominates(self, other: "VectorClock") -> bool:
        """True si self ocurrió después de other (causal)."""
        return self.compare(other) == VCRelation.AFTER

    # ── Serialización ─────────────────────────────────────────

    def to_dict(self) -> dict[str, int]:
        return {"beijing": self.beijing, "ukraine": self.ukraine, "lapaz": self.lapaz}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls, d: dict) -> "VectorClock":
        return cls(
            beijing=int(d.get("beijing", 0)),
            ukraine=int(d.get("ukraine", 0)),
            lapaz  =int(d.get("lapaz",   0)),
        )

    @classmethod
    def from_json(cls, s: str) -> "VectorClock":
        return cls.from_dict(json.loads(s))

    @classmethod
    def zero(cls) -> "VectorClock":
        return cls(0, 0, 0)

    def __repr__(self) -> str:
        return f"VC(bej={self.beijing}, ukr={self.ukraine}, lpz={self.lapaz})"


def resolve_conflict(vc1: VectorClock, ts1: float,
                     vc2: VectorClock, ts2: float) -> int:
    """
    Resuelve un conflicto entre dos operaciones concurrentes.
    Retorna 1 si gana vc1, 2 si gana vc2.

    Política: first-timestamp-wins (la reserva más antigua prevalece).
    Es determinística y auditable.
    """
    if ts1 <= ts2:
        return 1
    return 2
