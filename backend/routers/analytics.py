"""
routers/analytics.py
─────────────────────
Dashboard analytics — métricas en tiempo real del sistema.

  GET /analytics/summary   KPIs globales del sistema
"""
import asyncio
import logging
from collections import defaultdict

from fastapi import APIRouter

from db import sqlserver, mongodb
from sync.synchronizer import node_states

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["Analytics"])


async def _get_all_reservations() -> list[dict]:
    """Obtiene todas las reservas de cualquier nodo disponible."""
    rows: list[dict] = []
    for node in ("beijing", "ukraine"):
        if node_states[node].is_online:
            try:
                rows = await asyncio.to_thread(_sql_all_reservations, node)
                if rows:
                    return rows
            except Exception:
                pass
    if not rows and node_states["lapaz"].is_online:
        try:
            rows = await _mongo_all_reservations()
        except Exception:
            pass
    return rows


def _sql_all_reservations(node: str) -> list[dict]:
    from db.sqlserver import get_conn
    with get_conn(node) as conn:
        cursor = conn.execute("""
            SELECT r.status, r.cabin_class, r.price_paid, r.node_origin,
                   f.origin, f.destination, r.created_at
            FROM reservations r
            JOIN flights f ON f.id = r.flight_id
            WHERE r.status IN ('CONFIRMED', 'RESERVED')
        """)
        cols = [c[0] for c in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]


async def _mongo_all_reservations() -> list[dict]:
    from db.mongodb import get_async_db
    db = get_async_db()
    pipeline = [
        {"$match": {"status": {"$in": ["CONFIRMED", "RESERVED"]}}},
        {"$lookup": {
            "from": "flights",
            "localField": "flight_id",
            "foreignField": "id",
            "as": "flight",
        }},
        {"$project": {
            "_id": 0,
            "status": 1,
            "cabin_class": 1,
            "price_paid": 1,
            "node_origin": 1,
            "created_at": 1,
            "origin":      {"$arrayElemAt": ["$flight.origin", 0]},
            "destination": {"$arrayElemAt": ["$flight.destination", 0]},
        }},
    ]
    return await db.reservations.aggregate(pipeline).to_list(length=None)


async def _get_all_flights() -> list[dict]:
    """Obtiene todos los vuelos futuros para calcular ocupación."""
    for node in ("beijing", "ukraine"):
        if node_states[node].is_online:
            try:
                rows = await asyncio.to_thread(
                    sqlserver.get_flights, node,
                    {"min_date": "2020-01-01"}
                )
                if rows:
                    return rows
            except Exception:
                pass
    if node_states["lapaz"].is_online:
        try:
            return await mongodb.get_flights({"min_date": "2020-01-01"})
        except Exception:
            pass
    return []


@router.get("/summary")
async def get_summary():
    """
    Retorna KPIs del sistema distribuido:
    - Total reservas CONFIRMED / RESERVED
    - Revenue total y por nodo
    - Reservas por clase de cabina
    - Top 5 rutas más vendidas
    - Reservas por nodo origen
    - Ocupación promedio (vuelos cargados)
    """
    reservations, flights = await asyncio.gather(
        _get_all_reservations(),
        _get_all_flights(),
    )

    total_confirmed  = 0
    total_reserved   = 0
    revenue_total    = 0.0
    revenue_by_node: dict[str, float]  = defaultdict(float)
    by_cabin:        dict[str, int]    = defaultdict(int)
    by_node:         dict[str, int]    = defaultdict(int)
    route_counts:    dict[str, int]    = defaultdict(int)

    for r in reservations:
        status = r.get("status", "")
        price  = float(r.get("price_paid") or 0)
        cabin  = r.get("cabin_class", "ECONOMY")
        node   = r.get("node_origin", "unknown")
        orig   = r.get("origin", "?")
        dest   = r.get("destination", "?")

        if status == "CONFIRMED":
            total_confirmed += 1
            revenue_total   += price
            revenue_by_node[node] += price
        elif status == "RESERVED":
            total_reserved += 1

        by_cabin[cabin] += 1
        by_node[node]   += 1
        if orig and dest:
            route_counts[f"{orig}→{dest}"] += 1

    top_routes = sorted(route_counts.items(), key=lambda x: -x[1])[:5]

    # Ocupación de vuelos (usando datos de la matriz)
    total_seats_eco   = 0
    total_seats_first = 0
    sold_eco          = 0
    sold_first        = 0

    AIRCRAFT_TOTAL = {
        "A380":  {"eco": 439, "first": 10},
        "B777":  {"eco": 300, "first": 10},
        "A350":  {"eco": 250, "first": 12},
        "B787":  {"eco": 220, "first":  8},
    }

    for f in flights:
        ac   = str(f.get("aircraft_type", "B777"))
        cap  = AIRCRAFT_TOTAL.get(ac, AIRCRAFT_TOTAL["B777"])
        avail_eco   = int(f.get("available_economy", cap["eco"]) or cap["eco"])
        avail_first = int(f.get("available_first",   cap["first"]) or cap["first"])

        total_seats_eco   += cap["eco"]
        total_seats_first += cap["first"]
        sold_eco          += max(0, cap["eco"]   - avail_eco)
        sold_first        += max(0, cap["first"] - avail_first)

    occ_eco   = round(sold_eco   / total_seats_eco   * 100, 1) if total_seats_eco   else 0
    occ_first = round(sold_first / total_seats_first * 100, 1) if total_seats_first else 0

    return {
        "total_confirmed":  total_confirmed,
        "total_reserved":   total_reserved,
        "total_bookings":   total_confirmed + total_reserved,
        "revenue_total":    round(revenue_total, 2),
        "revenue_by_node":  dict(revenue_by_node),
        "by_cabin":         dict(by_cabin),
        "by_node":          dict(by_node),
        "top_routes":       [{"route": r, "count": c} for r, c in top_routes],
        "occupancy": {
            "economy":     occ_eco,
            "first_class": occ_first,
            "total_flights": len(flights),
        },
        "nodes_online": {
            n: node_states[n].is_online
            for n in ("beijing", "ukraine", "lapaz")
        },
    }
