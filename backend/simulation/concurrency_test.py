"""
simulation/concurrency_test.py
────────────────────────────────
Simula operaciones concurrentes de reserva y anulación entre nodos
para validar que los Relojes Vectoriales resuelven conflictos
correctamente.

Escenarios simulados:
  1. Reservas simultáneas del mismo asiento en 2 nodos → conflicto → resolución
  2. Venta en nodo A mientras nodo B está caído → sync al reconectar
  3. Anulación concurrente → validar orden causal
  4. Cascada de 10 reservas rápidas con VCs entrelazados

Uso:
  python -m simulation.concurrency_test
"""
import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sync.vector_clock import VectorClock, VCRelation, resolve_conflict
from sync.ikj import IKJGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ── Simulación de nodo ────────────────────────────────────────

@dataclass
class SimNode:
    name: str
    vc: VectorClock
    ikj: IKJGenerator
    reservations: list  # historial local
    is_online: bool = True
    pending_sync: list = None  # operaciones no sincronizadas

    def __post_init__(self):
        if self.pending_sync is None:
            self.pending_sync = []


async def simulate_reservation(node: SimNode, flight_id: int,
                                seat: str, passenger: str) -> dict:
    """Simula crear una reserva en un nodo."""
    node.vc = node.vc.tick(node.name)
    res_id = await node.ikj.next_reservation_id()
    tx_id  = await node.ikj.next_transaction_id()
    ts     = time.time()

    reservation = {
        "id":           res_id,
        "transaction_id": tx_id,
        "flight_id":    flight_id,
        "passenger":    passenger,
        "seat":         seat,
        "node_origin":  node.name,
        "vector_clock": node.vc.to_dict(),
        "timestamp":    ts,
        "status":       "CONFIRMED",
    }
    node.reservations.append(reservation)
    logger.info("[%s] Reserva creada → %s | Asiento: %s | VC: %s",
                node.name, tx_id, seat, node.vc)
    return reservation


async def simulate_cancel(node: SimNode, transaction_id: str) -> None:
    """Simula cancelar una reserva en un nodo."""
    node.vc = node.vc.tick(node.name)
    for r in node.reservations:
        if r["transaction_id"] == transaction_id:
            r["status"] = "CANCELLED"
            r["cancel_vc"] = node.vc.to_dict()
            logger.info("[%s] Reserva cancelada → %s | VC: %s",
                        node.name, transaction_id, node.vc)
            return


def sync_nodes(sender: SimNode, receiver: SimNode) -> None:
    """Simula sincronización entre dos nodos (merge de VC)."""
    if not receiver.is_online:
        sender.pending_sync.extend(
            {"target": receiver.name, "vc": r["vector_clock"], "data": r}
            for r in sender.reservations[-1:]
        )
        logger.warning("[sync] %s está offline — operación encolada para sincronizar después",
                       receiver.name)
        return

    old_vc = receiver.vc
    receiver.vc = receiver.vc.merge(sender.vc, receiver.name)
    logger.info("[sync] %s → %s | VC antes: %s | VC después: %s",
                sender.name, receiver.name, old_vc, receiver.vc)


def replay_pending(node: SimNode, source: SimNode) -> None:
    """Reproduce operaciones pendientes cuando un nodo vuelve online."""
    logger.info("[sync] Reproduciendo %d operaciones pendientes en %s...",
                len(source.pending_sync), node.name)

    # Ordenar por suma del VC (causal)
    pending = sorted(
        source.pending_sync,
        key=lambda x: sum(x["vc"].values())
    )
    for op in pending:
        node.vc = node.vc.merge(
            VectorClock.from_dict(op["vc"]), node.name
        )
        node.reservations.append(op["data"])
        logger.info("[replay] Operación %s aplicada en %s",
                    op["data"]["transaction_id"], node.name)

    source.pending_sync.clear()


def detect_conflict(r1: dict, r2: dict) -> bool:
    """Detecta si dos reservas son concurrentes para el mismo asiento."""
    if r1["flight_id"] != r2["flight_id"]:
        return False
    if r1["seat"] != r2["seat"]:
        return False
    vc1 = VectorClock.from_dict(r1["vector_clock"])
    vc2 = VectorClock.from_dict(r2["vector_clock"])
    relation = vc1.compare(vc2)
    return relation == VCRelation.CONCURRENT


def resolve_seat_conflict(r1: dict, r2: dict) -> dict:
    """Resuelve un conflicto de asiento; retorna la reserva ganadora."""
    winner_idx = resolve_conflict(
        VectorClock.from_dict(r1["vector_clock"]), r1["timestamp"],
        VectorClock.from_dict(r2["vector_clock"]), r2["timestamp"],
    )
    winner = r1 if winner_idx == 1 else r2
    loser  = r2 if winner_idx == 1 else r1
    loser["status"] = "CANCELLED"
    loser["cancel_reason"] = "CONFLICT_RESOLVED"
    logger.info("[conflict] Ganador: %s | Perdedor: %s (first-ts-wins)",
                winner["transaction_id"], loser["transaction_id"])
    return winner


# ── Escenarios de simulación ──────────────────────────────────

async def scenario_1_double_booking():
    """Dos nodos reservan el mismo asiento simultáneamente."""
    logger.info("\n" + "="*60)
    logger.info("ESCENARIO 1: Double-booking concurrente (mismo asiento)")
    logger.info("="*60)

    beijing = SimNode("beijing", VectorClock.zero(), IKJGenerator("beijing"), [])
    ukraine = SimNode("ukraine", VectorClock.zero(), IKJGenerator("ukraine"), [])

    # Ambos nodos reservan 14A en el vuelo 1001 sin comunicarse
    r_bej = await simulate_reservation(beijing, 1001, "14A", "Pasaporte-CN-001")
    await asyncio.sleep(0.01)  # pequeño desfase temporal
    r_ukr = await simulate_reservation(ukraine, 1001, "14A", "Pasaporte-UA-002")

    # Detectar conflicto
    if detect_conflict(r_bej, r_ukr):
        logger.info("[conflict] Conflicto detectado para asiento 14A en vuelo 1001")
        winner = resolve_seat_conflict(r_bej, r_ukr)
        logger.info("[conflict] Resolución: %s confirmada, otra CANCELADA", winner["transaction_id"])
    else:
        logger.info("[OK] Sin conflicto (orden causal correcto)")


async def scenario_2_offline_node():
    """Reserva mientras un nodo está caído, sync al reconectar."""
    logger.info("\n" + "="*60)
    logger.info("ESCENARIO 2: Nodo caído — sync al reconectar")
    logger.info("="*60)

    beijing = SimNode("beijing", VectorClock.zero(), IKJGenerator("beijing"), [])
    ukraine = SimNode("ukraine", VectorClock.zero(), IKJGenerator("ukraine"), [], is_online=False)

    # Beijing crea reservas mientras Ucrania está offline
    r1 = await simulate_reservation(beijing, 2001, "5B", "Pasaporte-US-010")
    r2 = await simulate_reservation(beijing, 2001, "5C", "Pasaporte-US-011")

    sync_nodes(beijing, ukraine)  # Ucrania offline → encolado
    sync_nodes(beijing, ukraine)

    # Ucrania vuelve online
    logger.info("[sim] Nodo Ukraine vuelve ONLINE")
    ukraine.is_online = True
    replay_pending(ukraine, beijing)

    logger.info("[result] Ukraine ahora tiene %d reservas", len(ukraine.reservations))
    logger.info("[result] VC Ukraine: %s", ukraine.vc)


async def scenario_3_cancel_concurrent():
    """Anulación concurrente — verificar orden causal."""
    logger.info("\n" + "="*60)
    logger.info("ESCENARIO 3: Anulaciones concurrentes — orden causal")
    logger.info("="*60)

    lapaz = SimNode("lapaz", VectorClock.zero(), IKJGenerator("lapaz"), [])
    beijing = SimNode("beijing", VectorClock.zero(), IKJGenerator("beijing"), [])

    # La Paz crea reserva y la comparte con Beijing
    r = await simulate_reservation(lapaz, 3001, "22F", "Pasaporte-BO-020")
    sync_nodes(lapaz, beijing)

    # Ambos intentan cancelar (concurrente)
    await simulate_cancel(lapaz, r["transaction_id"])
    await simulate_cancel(beijing, r["transaction_id"])

    # Comparar VCs de las anulaciones
    vc_lapaz  = VectorClock.from_dict(next(x for x in lapaz.reservations
                                          if x["transaction_id"] == r["transaction_id"])
                                      .get("cancel_vc", lapaz.vc.to_dict()))
    vc_beijing = VectorClock.from_dict(next(x for x in beijing.reservations
                                           if x["transaction_id"] == r["transaction_id"])
                                       .get("cancel_vc", beijing.vc.to_dict()))

    relation = vc_lapaz.compare(vc_beijing)
    logger.info("[result] Relación VC anulaciones: %s", relation.value)


async def scenario_4_cascade_reservations():
    """10 reservas rápidas con VCs entrelazados entre 3 nodos."""
    logger.info("\n" + "="*60)
    logger.info("ESCENARIO 4: Cascada de 10 reservas entre 3 nodos")
    logger.info("="*60)

    nodes = {
        "beijing": SimNode("beijing", VectorClock.zero(), IKJGenerator("beijing"), []),
        "ukraine": SimNode("ukraine", VectorClock.zero(), IKJGenerator("ukraine"), []),
        "lapaz":   SimNode("lapaz",   VectorClock.zero(), IKJGenerator("lapaz"),   []),
    }

    seats = [f"{r}{c}" for r in range(1, 6) for c in "ABCDEF"]

    for i in range(10):
        node_name = random.choice(list(nodes.keys()))
        node = nodes[node_name]
        seat = seats[i]
        passenger = f"Pasaporte-{i:03d}"

        r = await simulate_reservation(node, 4001, seat, passenger)

        # Sync con los otros 2 nodos
        for other_name, other in nodes.items():
            if other_name != node_name:
                sync_nodes(node, other)

    # Mostrar estado final de VCs
    logger.info("\n[result] Estado final de Vector Clocks:")
    for name, node in nodes.items():
        logger.info("  %s → %s | Reservas: %d",
                    name, node.vc, len(node.reservations))


# ── Runner principal ──────────────────────────────────────────

async def run_all_scenarios():
    await scenario_1_double_booking()
    await scenario_2_offline_node()
    await scenario_3_cancel_concurrent()
    await scenario_4_cascade_reservations()
    logger.info("\n=== Simulación completa ===")


if __name__ == "__main__":
    asyncio.run(run_all_scenarios())
