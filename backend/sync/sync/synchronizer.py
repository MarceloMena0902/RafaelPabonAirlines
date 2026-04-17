"""
sync/synchronizer.py
────────────────────
Motor de sincronización entre los 3 nodos (CP).

Responsabilidades:
  1. Healthcheck periódico de los 3 nodos.
  2. Replicar escrituras a todos los nodos disponibles.
  3. Si un nodo está caído, encolar la operación en sync_queue.
  4. Cuando un nodo vuelve online, reproducir su cola en orden causal
     (ordenado por vector clock).
  5. Detectar y resolver conflictos (double-booking de asientos).

Diseño:
  • run_sync_loop() se llama como background task de FastAPI.
  • NodeState almacena el estado en memoria (vc + online flag).
  • Cada escritura pasa por broadcast_write() que intenta los 3 nodos.
"""
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field

from config import settings
from db import mongodb, sqlserver
from sync.vector_clock import VectorClock, VCRelation, resolve_conflict

logger = logging.getLogger(__name__)

# ── Estado global de los nodos ────────────────────────────────

@dataclass
class NodeState:
    name: str
    is_online: bool = False
    vector_clock: VectorClock = field(default_factory=VectorClock.zero)


# Instancias únicas compartidas en toda la app
node_states: dict[str, NodeState] = {
    "beijing": NodeState("beijing"),
    "ukraine": NodeState("ukraine"),
    "lapaz":   NodeState("lapaz"),
}


# ── Healthcheck ───────────────────────────────────────────────

async def check_node_health() -> dict[str, bool]:
    """
    Verifica disponibilidad de los 3 nodos y actualiza node_states.
    Retorna {node_name: is_online}.
    """
    results: dict[str, bool] = {}

    # SQL Server Beijing y Ucrania (síncrono en thread pool)
    for sql_node in ("beijing", "ukraine"):
        was_online = node_states[sql_node].is_online
        online = await asyncio.to_thread(sqlserver.is_online, sql_node)
        node_states[sql_node].is_online = online
        results[sql_node] = online

        if not was_online and online:
            logger.info("[sync] Nodo %s volvió online — iniciando replay", sql_node)
            asyncio.create_task(replay_sync_queue(sql_node))

    # MongoDB La Paz (asíncrono directo)
    was_online = node_states["lapaz"].is_online
    online = await mongodb.is_online()
    node_states["lapaz"].is_online = online
    results["lapaz"] = online

    if not was_online and online:
        logger.info("[sync] Nodo lapaz volvió online — iniciando replay")
        asyncio.create_task(replay_sync_queue("lapaz"))

    # Actualizar heartbeat en MongoDB (solo si lapaz está online)
    if node_states["lapaz"].is_online:
        for node_name, state in node_states.items():
            try:
                await mongodb.update_heartbeat(
                    node_name, state.is_online, state.vector_clock.to_dict()
                )
            except Exception:
                pass  # No queremos que el heartbeat rompa el loop

    return results


# ── Broadcast de escrituras ───────────────────────────────────

async def broadcast_write(operation_type: str, data: dict,
                          vector_clock: VectorClock,
                          origin_node: str) -> VectorClock:
    """
    Intenta replicar una operación a los 3 nodos.
    - Si un nodo está caído → encola en sync_queue del nodo origen.
    - Retorna el VC actualizado tras la operación.

    operation_type: "CREATE_RESERVATION" | "CANCEL_RESERVATION"
    """
    vc = vector_clock.tick(origin_node)
    vc_json = vc.to_json()
    data["vector_clock"] = vc_json

    tasks = {
        "beijing": _write_to_sql("beijing", operation_type, data, vc_json),
        "ukraine": _write_to_sql("ukraine", operation_type, data, vc_json),
        "lapaz":   _write_to_mongo(operation_type, data, vc_json),
    }

    for node_name, coro in tasks.items():
        if not node_states[node_name].is_online:
            # Nodo caído → encolar operación
            await _enqueue(origin_node, operation_type, node_name, data, vc_json)
            continue
        try:
            await coro
            # Actualizar VC en memoria del nodo destino
            node_states[node_name].vector_clock = (
                node_states[node_name].vector_clock.merge(vc, node_name)
            )
        except Exception as exc:
            logger.warning("[sync] Fallo al escribir en %s: %s", node_name, exc)
            node_states[node_name].is_online = False
            await _enqueue(origin_node, operation_type, node_name, data, vc_json)

    return vc


async def _write_to_sql(node: str, op_type: str, data: dict, vc_json: str) -> None:
    if op_type == "CREATE_RESERVATION":
        await asyncio.to_thread(sqlserver.insert_reservation, node, data)
    elif op_type == "CANCEL_RESERVATION":
        await asyncio.to_thread(
            sqlserver.cancel_reservation, node, data["transaction_id"], vc_json
        )


async def _write_to_mongo(op_type: str, data: dict, vc_json: str) -> None:
    if op_type == "CREATE_RESERVATION":
        await mongodb.insert_reservation(data)
    elif op_type == "CANCEL_RESERVATION":
        await mongodb.cancel_reservation(data["transaction_id"], vc_json)


async def _enqueue(origin_node: str, op_type: str, target_node: str,
                   data: dict, vc_json: str) -> None:
    """Encola en el nodo origen (el que sí está disponible)."""
    try:
        if origin_node in ("beijing", "ukraine"):
            await asyncio.to_thread(
                sqlserver.enqueue_sync,
                origin_node, data["transaction_id"], op_type,
                target_node, data, vc_json,
            )
        else:
            await mongodb.enqueue_sync(
                data["transaction_id"], op_type, target_node, data, vc_json
            )
    except Exception as exc:
        logger.error("[sync] No se pudo encolar operación para %s: %s", target_node, exc)


# ── Replay de la cola de sincronización ───────────────────────

async def replay_sync_queue(recovered_node: str) -> None:
    """
    Cuando un nodo vuelve online, replica todas las operaciones
    pendientes en orden causal (menor VC primero).
    """
    logger.info("[sync] Reproduciendo cola para nodo %s...", recovered_node)

    pending: list[dict] = []

    # Recolectar pendientes de los nodos que estaban online
    for source_node in ("beijing", "ukraine", "lapaz"):
        if source_node == recovered_node:
            continue
        if not node_states[source_node].is_online:
            continue
        try:
            if source_node in ("beijing", "ukraine"):
                items = await asyncio.to_thread(
                    sqlserver.get_pending_sync, source_node, recovered_node
                )
            else:
                items = await mongodb.get_pending_sync(recovered_node)
            pending.extend(items)
        except Exception as exc:
            logger.warning("[sync] No se pudo leer cola de %s: %s", source_node, exc)

    # Ordenar por vector clock (causal) y luego timestamp
    pending.sort(key=lambda x: (
        VectorClock.from_json(x["vector_clock"]).beijing +
        VectorClock.from_json(x["vector_clock"]).ukraine +
        VectorClock.from_json(x["vector_clock"]).lapaz,
        x.get("queued_at", "")
    ))

    for item in pending:
        payload = item["payload"] if isinstance(item["payload"], dict) else json.loads(item["payload"])
        op_type  = item["operation_type"]
        vc_json  = item["vector_clock"]

        try:
            if recovered_node in ("beijing", "ukraine"):
                await _write_to_sql(recovered_node, op_type, payload, vc_json)
            else:
                await _write_to_mongo(op_type, payload, vc_json)

            # Marcar como reproducida
            for source in ("beijing", "ukraine", "lapaz"):
                if source == recovered_node:
                    continue
                if not node_states[source].is_online:
                    continue
                try:
                    if source in ("beijing", "ukraine"):
                        await asyncio.to_thread(
                            sqlserver.mark_sync_replayed, source, item["id"]
                        )
                    else:
                        await mongodb.mark_sync_replayed(
                            item["transaction_id"], recovered_node
                        )
                except Exception:
                    pass

        except Exception as exc:
            logger.error("[sync] Error reproduciendo %s en %s: %s",
                         item["transaction_id"], recovered_node, exc)

    logger.info("[sync] Replay completado para %s (%d operaciones)", recovered_node, len(pending))


# ── Loop principal ────────────────────────────────────────────

async def run_sync_loop() -> None:
    """
    Tarea de fondo de FastAPI.
    Ejecuta healthcheck y sincronización cada SYNC_INTERVAL_SECONDS.
    """
    logger.info("[sync] Loop de sincronización iniciado (intervalo: %ds)",
                settings.sync_interval_seconds)
    while True:
        try:
            statuses = await check_node_health()
            offline = [n for n, ok in statuses.items() if not ok]
            if offline:
                logger.warning("[sync] Nodos OFFLINE: %s", offline)
        except Exception as exc:
            logger.error("[sync] Error en healthcheck: %s", exc)

        await asyncio.sleep(settings.sync_interval_seconds)


def get_offline_nodes() -> list[str]:
    """Devuelve la lista de nodos actualmente caídos (para el frontend)."""
    return [name for name, state in node_states.items() if not state.is_online]
