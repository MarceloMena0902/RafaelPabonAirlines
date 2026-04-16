import json
from dataclasses import dataclass, field
from enum import Enum


class VCRelation(Enum):
    BEFORE     = "BEFORE"
    AFTER      = "AFTER"
    EQUAL      = "EQUAL"
    CONCURRENT = "CONCURRENT"


@dataclass
class VectorClock:
    beijing: int = 0
    ukraine: int = 0
    lapaz:   int = 0

    def tick(self, node: str) -> "VectorClock":
        d = self.__dict__.copy()
        d[node] = d[node] + 1
        return VectorClock(**d)

    def merge(self, other: "VectorClock", local_node: str) -> "VectorClock":
        merged = VectorClock(
            beijing = max(self.beijing, other.beijing),
            ukraine = max(self.ukraine, other.ukraine),
            lapaz   = max(self.lapaz,   other.lapaz),
        )
        return merged.tick(local_node)

    def compare(self, other: "VectorClock") -> VCRelation:
        self_le  = self.beijing <= other.beijing and self.ukraine <= other.ukraine and self.lapaz <= other.lapaz
        other_le = other.beijing <= self.beijing and other.ukraine <= self.ukraine and other.lapaz <= self.lapaz
        if self_le and other_le:  return VCRelation.EQUAL
        if self_le:               return VCRelation.BEFORE
        if other_le:              return VCRelation.AFTER
        return VCRelation.CONCURRENT

    def to_json(self) -> str:
        return json.dumps({"beijing": self.beijing, "ukraine": self.ukraine, "lapaz": self.lapaz})

    @classmethod
    def from_json(cls, s: str) -> "VectorClock":
        d = json.loads(s)
        return cls(beijing=d.get("beijing", 0), ukraine=d.get("ukraine", 0), lapaz=d.get("lapaz", 0))


def resolve_conflict(vc1: VectorClock, ts1: float, vc2: VectorClock, ts2: float) -> int:
    """Devuelve 1 si vc1 gana, 2 si vc2 gana. Criterio: primer timestamp."""
    rel = vc1.compare(vc2)
    if rel == VCRelation.BEFORE:  return 2
    if rel == VCRelation.AFTER:   return 1
    return 1 if ts1 <= ts2 else 2
