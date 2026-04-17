"""
routers/reservations.py
────────────────────────
Endpoints de reservas: crear, cancelar y consultar.
"""
import asyncio
import logging
from fastapi import APIRouter, HTTPException
from db import sqlserver, mongodb
from geo.proximity import blocked_airports, node_for_airport
from models.schemas import ReservationRequest, ReservationResponse, CancelRequest
from sync.ikj import IKJGenerator
from sync.synchronizer import node_states, broadcast_write, get_offline_nodes
from sync.vector_clock import VectorClock
from data.matrices import PRICES_ECONOMY, PRICES_FIRST

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reservations", tags=["Reservas"])

_ikj: dict[str, IKJGenerator] = {
    "beijing": IKJGenerator("beijing"),
    "ukraine": IKJGenerator("ukraine"),
    "lapaz":   IKJGenerator("lapaz"),
}


def _determine_serving_node() -> str:
    for node in ("lapaz", "beijing", "ukraine"):
        if node_states[node].is_online:
            return node
    raise HTTPException(status_code=503, detail="Todos los nodos están fuera de línea.")


async def _get_flight(flight_id: int) -> dict:
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


@router.post("/", response_model=ReservationResponse, status_code=201)
async def create_reservation(req: ReservationRequest):
    flight  = await _get_flight(req.flight_id)
    offline = get_offline_nodes()
    blocked = set(blocked_airports(offline))

    for airport in (flight["origin"], flight["destination"]):
        if airport in blocked:
            node = node_for_airport(airport)
            raise HTTPException(status_code=503, detail={
                "message":          "No se pueden realizar compras para esta ruta.",
                "reason":           f"El nodo regional '{node}' no está disponible.",
                "affected_airport": airport,
                "blocked_airports": list(blocked),
            })

    field = "available_first" if req.cabin_class == "FIRST" else "available_economy"
    if flight.get(field, 0) <= 0:
        raise HTTPException(status_code=409, detail="No hay asientos disponibles.")

    serving_node   = _determine_serving_node()
    ikj            = _ikj[serving_node]
    reservation_id = await ikj.next_reservation_id()
    transaction_id = await ikj.next_transaction_id()

    price = float(flight.get("price_first" if req.cabin_class == "FIRST" else "price_economy", 0))

    current_vc = node_states[serving_node].vector_clock
    new_vc     = current_vc.tick(serving_node)

    data = {
        "id":                 reservation_id,
        "transaction_id":     transaction_id,
        "flight_id":          req.flight_id,
        "passenger_passport": req.passenger_passport,
        "seat_number":        req.seat_number,
        "cabin_class":        req.cabin_class,
        "status":             "CONFIRMED",
        "price_paid":         price,
        "node_origin":        serving_node,
        "vector_clock":       new_vc.to_json(),
    }

    final_vc = await broadcast_write("CREATE_RESERVATION", data, current_vc, serving_node)
    node_states[serving_node].vector_clock = final_vc

    return ReservationResponse(**data)


@router.delete("/", status_code=200)
async def cancel_reservation(req: CancelRequest):
    serving_node = _determine_serving_node()
    current_vc   = node_states[serving_node].vector_clock
    data         = {"transaction_id": req.transaction_id}
    final_vc     = await broadcast_write("CANCEL_RESERVATION", data, current_vc, serving_node)
    node_states[serving_node].vector_clock = final_vc
    return {"message": "Reserva cancelada.", "transaction_id": req.transaction_id}


@router.get("/flight/{flight_id}")
async def get_reservations_for_flight(flight_id: int):
    for node in ("beijing", "ukraine"):
        if node_states[node].is_online:
            try:
                return await asyncio.to_thread(sqlserver.get_reservations_for_flight, node, flight_id)
            except Exception:
                pass
    if node_states["lapaz"].is_online:
        return await mongodb.get_reservations_for_flight(flight_id)
    raise HTTPException(status_code=503, detail="Sin nodos disponibles.")


@router.get("/flight/{flight_id}/seats")
async def get_seats_for_flight(flight_id: int):
    """
    Devuelve todos los asientos con estado CONFIRMED o RESERVED,
    incluyendo datos del pasajero (passport + nombre completo).
    Respuesta: lista de { seat_number, status, cabin_class,
                          passenger_passport, passenger_name, transaction_id }
    """
    for node in ("beijing", "ukraine"):
        if node_states[node].is_online:
            try:
                return await asyncio.to_thread(sqlserver.get_seats_for_flight, node, flight_id)
            except Exception:
                pass
    if node_states["lapaz"].is_online:
        return await mongodb.get_seats_for_flight(flight_id)
    raise HTTPException(status_code=503, detail="Sin nodos disponibles.")
