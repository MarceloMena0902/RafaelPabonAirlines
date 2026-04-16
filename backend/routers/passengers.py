"""
routers/passengers.py
──────────────────────
Consulta de pasajeros por pasaporte.
"""
import asyncio
from fastapi import APIRouter, HTTPException
from db import sqlserver, mongodb
from sync.synchronizer import node_states

router = APIRouter(prefix="/passengers", tags=["Pasajeros"])


@router.get("/{passport}")
async def get_passenger(passport: str):
    passport = passport.upper()
    for node in ("beijing", "ukraine"):
        if node_states[node].is_online:
            try:
                result = await asyncio.to_thread(sqlserver.get_passenger, node, passport)
                if result:
                    return result
            except Exception:
                pass
    if node_states["lapaz"].is_online:
        result = await mongodb.get_passenger(passport)
        if result:
            return result
    raise HTTPException(status_code=404, detail="Pasajero no encontrado.")
