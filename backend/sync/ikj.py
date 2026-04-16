"""
Identity Key Jumping (IKJ)
Rangos de IDs únicos por nodo:
  Beijing  → 1 000 000 000+
  Ucrania  → 2 000 000 000+
  La Paz   → 3 000 000 000+
"""
import asyncio
import time


class IKJGenerator:
    OFFSETS = {"beijing": 1_000_000_000, "ukraine": 2_000_000_000, "lapaz": 3_000_000_000}

    def __init__(self, node: str):
        self.node   = node
        self.offset = self.OFFSETS[node]
        self._seq   = 0
        self._lock  = asyncio.Lock()

    async def next_reservation_id(self) -> int:
        async with self._lock:
            self._seq += 1
            return self.offset + self._seq

    async def next_transaction_id(self) -> str:
        async with self._lock:
            ts  = int(time.time() * 1000)
            seq = self._seq
            prefix = {"beijing": "BEJ", "ukraine": "UKR", "lapaz": "LPZ"}[self.node]
            return f"{prefix}-{ts}-{seq:06d}"
