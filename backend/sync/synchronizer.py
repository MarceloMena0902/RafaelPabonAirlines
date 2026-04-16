"""
synchronizer.py
────────────────
Gestiona el estado de los 3 nodos y la replicación de operaciones.
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field

from sync.vector_clock import VectorClock

logger = logging.getLogger(__name__)


@dataclass
class NodeState:
    is_online:    bool        = False
    vector_clock: VectorClock = field(default_factory=VectorClock)
    sync_queue:   list        = field(default_factory=list)


node_states: dict[str, NodeState] = {
    "beijing": NodeState(),
    "ukraine": NodeState(),
    "lapaz":   NodeState(),
}


def get_offline_nodes() -> list[str]:
    return [n for n, s in node_states.items() if not s.is_online]


async def check_node_health() -> None:
    from db import sqlserver, mongodb

    for node in ("beijing", "ukraine"):
        try:
            online = await asyncio.to_thread(sqlserver.is_online, node)
        except Exception:
            online = False
        was_online = node_states[node].is_online
        node_states[node].is_online = online
        if not was_online and online:
            logger.info("[sync] %s reconectado — reproduciendo cola", node)
            asyncio.create_task(replay_sync_queue(node))

    try:
        online = await mongodb.is_online()
    except Exception:
        online = False
    was_online = node_states["lapaz"].is_online
    node_states["lapaz"].is_online = online
    if not was_online and online:
        logger.info("[sync] lapaz reconectado — reproduciendo cola")
        asyncio.create_task(replay_sync_queue("lapaz"))


async def broadcast_write(
    operation_type: str,
    data: dict,
    vector_clock: VectorClock,
    origin_node: str,
) -> VectorClock:
    from db import sqlserver, mongodb

    new_vc = vector_clock.tick(origin_node)

    async def write_to(node: str):
        if not node_states[node].is_online:
            node_states[node].sync_queue.append({
                "operation_type": operation_type,
                "data":           data,
                "vector_clock":   new_vc.to_json(),
            })
            return
        try:
            if operation_type == "CREATE_RESERVATION":
                if node in ("beijing", "ukraine"):
                    await asyncio.to_thread(sqlserver.insert_reservation, node, data)
                else:
                    await mongodb.insert_reservation(data)
            elif operation_type == "CANCEL_RESERVATION":
                tx_id = data["transaction_id"]
                if node in ("beijing", "ukraine"):
                    await asyncio.to_thread(sqlserver.cancel_reservation, node, tx_id, new_vc.to_json())
                else:
                    await mongodb.cancel_reservation(tx_id, new_vc.to_json())
        except Exception as exc:
            logger.error("[broadcast] Error escribiendo a %s: %s", node, exc)
            node_states[node].is_online = False
            node_states[node].sync_queue.append({
                "operation_type": operation_type,
                "data":           data,
                "vector_clock":   new_vc.to_json(),
            })

    await asyncio.gather(
        write_to("beijing"),
        write_to("ukraine"),
        write_to("lapaz"),
    )
    return new_vc


async def replay_sync_queue(recovered_node: str) -> None:
    from db import sqlserver, mongodb

    queue = node_states[recovered_node].sync_queue[:]
    node_states[recovered_node].sync_queue.clear()

    for op in queue:
        try:
            if op["operation_type"] == "CREATE_RESERVATION":
                if recovered_node in ("beijing", "ukraine"):
                    await asyncio.to_thread(sqlserver.insert_reservation, recovered_node, op["data"])
                else:
                    await mongodb.insert_reservation(op["data"])
            elif op["operation_type"] == "CANCEL_RESERVATION":
                tx_id = op["data"]["transaction_id"]
                if recovered_node in ("beijing", "ukraine"):
                    await asyncio.to_thread(sqlserver.cancel_reservation, recovered_node, tx_id, op["vector_clock"])
                else:
                    await mongodb.cancel_reservation(tx_id, op["vector_clock"])
        except Exception as exc:
            logger.error("[replay] Error en %s: %s", recovered_node, exc)


async def run_sync_loop() -> None:
    from config import settings
    while True:
        await asyncio.sleep(settings.sync_interval_seconds)
        await check_node_health()
