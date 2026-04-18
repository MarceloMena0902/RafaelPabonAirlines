"""
db/mongodb.py
─────────────
Gestiona la conexión al nodo MongoDB (La Paz) y expone las mismas
operaciones que sqlserver.py para que el synchronizer pueda tratarlos
de forma uniforme.

Motor (async) se usa para las operaciones llamadas desde los
endpoints FastAPI; pymongo síncrono para la ingesta en paralelo.
"""
import json
import logging
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from config import settings

logger = logging.getLogger(__name__)

# ── Cliente asíncrono (FastAPI / endpoints) ───────────────────
_async_client: AsyncIOMotorClient | None = None


def get_async_db():
    global _async_client
    if _async_client is None:
        _async_client = AsyncIOMotorClient(
            settings.mongo_uri(),
            serverSelectionTimeoutMS=5000,
        )
    return _async_client[settings.mongo_database]


# ── Cliente síncrono (ingesta paralela) ───────────────────────
def get_sync_db():
    client = MongoClient(
        settings.mongo_uri(),
        serverSelectionTimeoutMS=5000,
    )
    return client[settings.mongo_database]


# ── Healthcheck ───────────────────────────────────────────────

async def is_online() -> bool:
    try:
        db = get_async_db()
        await db.command("ping")
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError):
        return False


# ── Lectura: vuelos ───────────────────────────────────────────

async def get_flights(filters: dict | None = None) -> list[dict]:
    db = get_async_db()
    query: dict = {}
    if filters:
        if "origin" in filters:
            query["origin"] = filters["origin"]
        if "destination" in filters:
            query["destination"] = filters["destination"]
        if "flight_date" in filters:
            query["flight_date"] = filters["flight_date"]
        if "status" in filters:
            query["status"] = filters["status"]
        if "min_date" in filters:
            if "flight_date" in query:
                pass  # exact date takes precedence
            else:
                query["flight_date"] = {"$gte": filters["min_date"]}
        if filters.get("exclude_past"):
            query["status"] = {"$nin": ["ARRIVED", "CANCELLED"]}

    cursor = db.flights.find(query, {"_id": 0}).sort([("flight_date", 1), ("departure_time", 1)])
    return await cursor.to_list(length=None)


async def get_flight_by_id(flight_id: int) -> dict | None:
    db = get_async_db()
    return await db.flights.find_one({"id": flight_id}, {"_id": 0})


# ── Escritura: reservas ───────────────────────────────────────

async def insert_reservation(data: dict) -> None:
    """
    Inserta una reserva. El campo vector_clock es un string JSON
    para mantener consistencia con SQL Server.
    """
    db = get_async_db()
    doc = {**data, "created_at": datetime.now(timezone.utc),
                   "updated_at": datetime.now(timezone.utc)}
    await db.reservations.insert_one(doc)

    # Decrementar disponibilidad del vuelo
    field = "available_first" if data["cabin_class"] == "FIRST" else "available_economy"
    await db.flights.update_one(
        {"id": data["flight_id"]},
        {"$inc": {field: -1}}
    )


async def cancel_reservation(transaction_id: str, vector_clock: str) -> None:
    db = get_async_db()
    await db.reservations.update_one(
        {"transaction_id": transaction_id},
        {"$set": {"status": "CANCELLED",
                  "vector_clock": vector_clock,
                  "updated_at": datetime.now(timezone.utc)}}
    )


async def get_reservations_for_flight(flight_id: int) -> list[dict]:
    db = get_async_db()
    cursor = db.reservations.find(
        {"flight_id": flight_id, "status": "CONFIRMED"}, {"_id": 0}
    )
    return await cursor.to_list(length=None)


async def get_seats_for_flight(flight_id: int) -> list[dict]:
    """
    Devuelve todos los asientos ocupados (CONFIRMED o RESERVED) de un vuelo,
    incluyendo nombre del pasajero via $lookup a la colección passengers.
    """
    db = get_async_db()
    pipeline = [
        {"$match": {"flight_id": flight_id, "status": {"$in": ["CONFIRMED", "RESERVED"]}}},
        {"$lookup": {
            "from": "passengers",
            "localField": "passenger_passport",
            "foreignField": "passport",
            "as": "pax",
        }},
        {"$project": {
            "_id": 0,
            "seat_number": 1,
            "status": 1,
            "cabin_class": 1,
            "passenger_passport": 1,
            "transaction_id": 1,
            "passenger_name": {
                "$ifNull": [{"$arrayElemAt": ["$pax.full_name", 0]}, None]
            },
        }},
    ]
    return await db.reservations.aggregate(pipeline).to_list(length=None)


async def get_reservation_by_transaction_id(transaction_id: str) -> dict | None:
    db = get_async_db()
    doc = await db.reservations.find_one({"transaction_id": transaction_id}, {"_id": 0})
    return doc


# ── Lectura: pasajeros ────────────────────────────────────────

async def get_passenger(passport: str) -> dict | None:
    db = get_async_db()
    return await db.passengers.find_one({"passport": passport}, {"_id": 0})


# ── IKJ: siguiente ID para nodo La Paz ───────────────────────

async def next_reservation_id() -> int:
    """
    Usa findAndModify atómico para obtener el siguiente ID IKJ
    del nodo La Paz (rango 3_000_000_000+).
    """
    db = get_async_db()
    result = await db.ikj_counter.find_one_and_update(
        {"node": "lapaz"},
        {"$inc": {"next_id": 1}},
        return_document=True,
    )
    return result["next_id"]


# ── Sync queue ────────────────────────────────────────────────

async def enqueue_sync(transaction_id: str, operation_type: str,
                       target_node: str, payload: dict,
                       vector_clock: str) -> None:
    db = get_async_db()
    await db.sync_queue.insert_one({
        "transaction_id":  transaction_id,
        "operation_type":  operation_type,
        "target_node":     target_node,
        "payload":         payload,
        "vector_clock":    vector_clock,
        "queued_at":       datetime.now(timezone.utc),
        "replayed":        False,
    })


async def get_pending_sync(target_node: str) -> list[dict]:
    db = get_async_db()
    cursor = db.sync_queue.find(
        {"target_node": target_node, "replayed": False},
        {"_id": 0}
    ).sort("queued_at", 1)
    return await cursor.to_list(length=None)


async def mark_sync_replayed(transaction_id: str, target_node: str) -> None:
    db = get_async_db()
    await db.sync_queue.update_one(
        {"transaction_id": transaction_id, "target_node": target_node},
        {"$set": {"replayed": True}}
    )


# ── Heartbeat de nodos ────────────────────────────────────────

async def update_heartbeat(node: str, is_online_flag: bool, vc_dict: dict) -> None:
    db = get_async_db()
    await db.node_heartbeat.update_one(
        {"node": node},
        {"$set": {"is_online": is_online_flag,
                  "last_seen": datetime.now(timezone.utc),
                  "vector_clock": vc_dict}},
        upsert=True,
    )


async def get_all_heartbeats() -> list[dict]:
    db = get_async_db()
    cursor = db.node_heartbeat.find({}, {"_id": 0})
    return await cursor.to_list(length=None)
