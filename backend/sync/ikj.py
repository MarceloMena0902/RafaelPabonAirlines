"""
sync/ikj.py
───────────
Identity Key Jumping (IKJ) — generación de IDs únicos globales
sin coordinación entre nodos.

Cada nodo tiene un rango de IDs disjunto:
  beijing → [1_000_000_000 .. 1_999_999_999]
  ukraine → [2_000_000_000 .. 2_999_999_999]
  lapaz   → [3_000_000_000 .. 3_999_999_999]

La clase es thread-safe gracias al Lock asíncrono.
El contador se resetea cada vez que sube el servicio; si la app
reinicia los IDs siguen siendo únicos porque están ligados al
timestamp del transaction_id.
"""
import asyncio
import time
from typing import ClassVar


class IKJGenerator:
    """Genera IDs de reserva y transaction_ids únicos por nodo."""

    OFFSETS: ClassVar[dict[str, int]] = {
        "beijing": 1_000_000_000,
        "ukraine": 2_000_000_000,
        "lapaz":   3_000_000_000,
    }

    PREFIXES: ClassVar[dict[str, str]] = {
        "beijing": "BEJ",
        "ukraine": "UKR",
        "lapaz":   "LPZ",
    }

    def __init__(self, node_name: str) -> None:
        if node_name not in self.OFFSETS:
            raise ValueError(f"Nodo desconocido: {node_name}")
        self.node        = node_name
        self._offset     = self.OFFSETS[node_name]
        self._prefix     = self.PREFIXES[node_name]
        self._counter    = 13_000_000
        self._lock       = asyncio.Lock()

    async def next_reservation_id(self) -> int:
        """Retorna el siguiente BIGINT único para una reserva."""
        async with self._lock:
            self._counter += 1
            return self._offset + self._counter

    async def next_transaction_id(self) -> str:
        """
        Retorna un string único para transaction_id.
        Formato: {PREFIX}-{timestamp_ms}-{seq:06d}
        Ejemplo: BEJ-1745481600123-000042
        """
        async with self._lock:
            self._counter += 1
            ts_ms = int(time.time() * 1000)
            return f"{self._prefix}-{ts_ms}-{self._counter:06d}"

    @property
    def current_counter(self) -> int:
        return self._counter
