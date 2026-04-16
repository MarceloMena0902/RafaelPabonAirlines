"""
routers/flights.py
───────────────────
Búsqueda y detalle de vuelos.
"""
import asyncio
import logging
from fastapi import APIRouter, HTTPException
from db import sqlserver, mongodb
from sync.synchronizer import node_states

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/flights", tags=["Vuelos"])


@router.get("/")
async def search_flights(
    origin:      str | None = None,
    destination: str | None = None,
    flight_date: str | None = None,
    cabin_class: str | None = None,
):
    filters = {}
    if origin:      filters["origin"]      = origin.upper()
    if destination: filters["destination"] = destination.upper()
    if flight_date: filters["flight_date"] = flight_date

    for node in ("beijing", "ukraine"):
        if node_states[node].is_online:
            try:
                return await asyncio.to_thread(sqlserver.get_flights, node, filters)
            except Exception:
                pass
    if node_states["lapaz"].is_online:
        return await mongodb.get_flights(filters)
    raise HTTPException(status_code=503, detail="Sin nodos disponibles.")


@router.get("/{flight_id}")
async def get_flight(flight_id: int):
    for node in ("beijing", "ukraine"):
        if node_states[node].is_online:
            try:
                result = await asyncio.to_thread(sqlserver.get_flight_by_id, node, flight_id)
                if result:
                    return result
            except Exception:
                pass
    if node_states["lapaz"].is_online:
        result = await mongodb.get_flight_by_id(flight_id)
        if result:
            return result
    raise HTTPException(status_code=404, detail="Vuelo no encontrado.")
