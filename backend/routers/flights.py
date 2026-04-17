"""
routers/flights.py
───────────────────
Búsqueda y detalle de vuelos.
"""
import asyncio
import logging
import math
from datetime import datetime, date, timedelta, timezone

from fastapi import APIRouter, HTTPException
from db import sqlserver, mongodb
from sync.synchronizer import node_states
from geo.proximity import AIRPORT_COORDS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/flights", tags=["Vuelos"])


# ── Helpers para Flight Tracker ───────────────────────────────────

def _great_circle_position(
    lat1: float, lon1: float,
    lat2: float, lon2: float,
    fraction: float,
) -> tuple[float, float]:
    """
    Interpola una posición sobre el gran círculo entre dos puntos.
    fraction: 0.0 = origen, 1.0 = destino.
    Usa la fórmula de interpolación esférica (slerp simplificada).
    """
    fraction = max(0.0, min(1.0, fraction))

    # Convertir a radianes
    phi1    = math.radians(lat1)
    lam1    = math.radians(lon1)
    phi2    = math.radians(lat2)
    lam2    = math.radians(lon2)

    # Distancia angular
    d = math.acos(
        max(-1.0, min(1.0,
            math.sin(phi1) * math.sin(phi2)
            + math.cos(phi1) * math.cos(phi2) * math.cos(lam2 - lam1)
        ))
    )

    if d < 1e-9:
        return lat1, lon1

    A = math.sin((1 - fraction) * d) / math.sin(d)
    B = math.sin(fraction * d) / math.sin(d)

    x = A * math.cos(phi1) * math.cos(lam1) + B * math.cos(phi2) * math.cos(lam2)
    y = A * math.cos(phi1) * math.sin(lam1) + B * math.cos(phi2) * math.sin(lam2)
    z = A * math.sin(phi1)                  + B * math.sin(phi2)

    lat = math.degrees(math.atan2(z, math.sqrt(x * x + y * y)))
    lon = math.degrees(math.atan2(y, x))
    return round(lat, 4), round(lon, 4)


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


@router.get("/live")
async def get_live_flights():
    """
    Devuelve los vuelos que están en el aire ahora mismo.
    Para cada vuelo calcula la posición estimada usando el
    gran círculo entre origen y destino.

    Respuesta por vuelo:
      id, origin, destination, departure_time, duration_hours,
      fraction, lat, lon, heading, aircraft_type
    """
    now_utc = datetime.now(timezone.utc)
    today   = now_utc.date()

    flights_raw: list[dict] = []

    # Intentar obtener vuelos de hoy de SQL Server
    for node in ("beijing", "ukraine"):
        if node_states[node].is_online:
            try:
                rows = await asyncio.to_thread(
                    sqlserver.get_flights, node,
                    {"flight_date": str(today)}
                )
                if rows:
                    flights_raw = rows
                    break
            except Exception:
                pass

    # Si no hay SQL, intentar Mongo
    if not flights_raw and node_states["lapaz"].is_online:
        try:
            flights_raw = await mongodb.get_flights({"flight_date": str(today)})
        except Exception:
            pass

    live: list[dict] = []

    for f in flights_raw:
        origin      = f.get("origin", "")
        destination = f.get("destination", "")
        dep_time    = f.get("departure_time")    # time / str "HH:MM:SS"
        dur_hours   = f.get("duration_hours", 0) or 0
        flight_date = f.get("flight_date")       # date / str

        if not (origin in AIRPORT_COORDS and destination in AIRPORT_COORDS):
            continue
        if not dep_time or not dur_hours:
            continue

        # Construir datetime de salida (UTC naive → aware)
        try:
            if hasattr(flight_date, "year"):
                fd = flight_date
            else:
                fd = date.fromisoformat(str(flight_date))

            if hasattr(dep_time, "seconds"):          # timedelta (pyodbc)
                total_s  = dep_time.seconds
                dep_dt   = datetime(fd.year, fd.month, fd.day,
                                    total_s // 3600,
                                    (total_s % 3600) // 60,
                                    total_s % 60,
                                    tzinfo=timezone.utc)
            else:
                dep_str = str(dep_time)[:5]           # "HH:MM"
                h, m    = int(dep_str[:2]), int(dep_str[3:5])
                dep_dt  = datetime(fd.year, fd.month, fd.day, h, m,
                                   tzinfo=timezone.utc)

            arr_dt = dep_dt + timedelta(hours=float(dur_hours))

            if not (dep_dt <= now_utc <= arr_dt):
                continue

            elapsed_s = (now_utc - dep_dt).total_seconds()
            fraction  = elapsed_s / (float(dur_hours) * 3600)

        except Exception:
            continue

        o_lat, o_lon = AIRPORT_COORDS[origin]
        d_lat, d_lon = AIRPORT_COORDS[destination]
        cur_lat, cur_lon = _great_circle_position(
            o_lat, o_lon, d_lat, d_lon, fraction
        )

        # Heading aproximado (grados respecto al norte)
        delta_lon = math.radians(d_lon - o_lon)
        lat1r = math.radians(o_lat)
        lat2r = math.radians(d_lat)
        x = math.sin(delta_lon) * math.cos(lat2r)
        y = (math.cos(lat1r) * math.sin(lat2r)
             - math.sin(lat1r) * math.cos(lat2r) * math.cos(delta_lon))
        heading = (math.degrees(math.atan2(x, y)) + 360) % 360

        live.append({
            "id":           f.get("id"),
            "origin":       origin,
            "destination":  destination,
            "flight_date":  str(fd),
            "departure_time": str(dep_time)[:5] if not hasattr(dep_time, "seconds")
                              else f"{dep_dt.hour:02d}:{dep_dt.minute:02d}",
            "duration_hours": float(dur_hours),
            "fraction":     round(fraction, 4),
            "lat":          cur_lat,
            "lon":          cur_lon,
            "heading":      round(heading, 1),
            "aircraft_type": f.get("aircraft_type", ""),
            "node_owner":   f.get("node_owner", ""),
        })

    # ── Vuelo de prueba (siempre presente para validación) ──────────
    # Sale desde ATL hacia PEK, partió hace 45 minutos, duración 14h
    test_dep = now_utc - timedelta(minutes=45)
    test_dur = 14.0
    test_arr = test_dep + timedelta(hours=test_dur)
    if test_dep <= now_utc <= test_arr:
        t_frac = (now_utc - test_dep).total_seconds() / (test_dur * 3600)
        o_lat, o_lon = AIRPORT_COORDS["ATL"]
        d_lat, d_lon = AIRPORT_COORDS["PEK"]
        t_lat, t_lon = _great_circle_position(o_lat, o_lon, d_lat, d_lon, t_frac)
        delta_lon = math.radians(d_lon - o_lon)
        x = math.sin(delta_lon) * math.cos(math.radians(d_lat))
        y = (math.cos(math.radians(o_lat)) * math.sin(math.radians(d_lat))
             - math.sin(math.radians(o_lat)) * math.cos(math.radians(d_lat))
             * math.cos(delta_lon))
        hdg = (math.degrees(math.atan2(x, y)) + 360) % 360
        live.append({
            "id":           99999,
            "origin":       "ATL",
            "destination":  "PEK",
            "flight_date":  str(today),
            "departure_time": test_dep.strftime("%H:%M"),
            "duration_hours": test_dur,
            "fraction":     round(t_frac, 4),
            "lat":          t_lat,
            "lon":          t_lon,
            "heading":      round(hdg, 1),
            "aircraft_type": "B777",
            "node_owner":   "beijing",
            "is_demo":      True,
        })

    return live


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
