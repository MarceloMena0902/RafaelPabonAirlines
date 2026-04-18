"""
ingestion/fill_reservations.py  —  v3
──────────────────────────────────────────────────────────────────
Pre-llena la tabla reservations respetando:

  Regla 72h:
    • Vuelos PASADOS o con salida en las próximas 72h:
        → solo asientos CONFIRMED (vendidos)
        → sin RESERVED (la reserva ya no es válida o vence pronto)
    • Vuelos con salida a MÁS de 72h:
        → 73 % de asientos → CONFIRMED
        →  3 % de asientos → RESERVED
        → resto            → libre

  Los 3 nodos reciben exactamente los mismos datos (sistema CP).
  Primera clase también se llena proporcionalmente.

Uso:
  # Dentro del contenedor:
  python -m ingestion.fill_reservations
  python -m ingestion.fill_reservations --reset   # borra previas y recarga
  python -m ingestion.fill_reservations --local   # apunta a localhost
  python -m ingestion.fill_reservations --dry-run # solo muestra stats, no inserta
"""
import argparse
import logging
import math
import random
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pyodbc
from pymongo import MongoClient, InsertOne
from pymongo.errors import BulkWriteError

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
    force=True,
)
log = logging.getLogger(__name__)

# ── Porcentajes objetivo ───────────────────────────────────────
PCT_CONFIRMED = 0.73
PCT_RESERVED  = 0.03   # solo en vuelos con salida > 72h

# ── Tamaño de lote ─────────────────────────────────────────────
BATCH_FLIGHTS = 300

# ── Distribuciones reales de cabina (idéntico a SeatMap.jsx) ──
_AIRCRAFT = {
    1: {
        "type": "A380",
        "first_seats": 10, "eco_seats": 439,
        "first_groups": [["A","B"], ["C","D"]],
        "eco_groups":   [["A","B","C"], ["D","E","F","G"], ["H","J","K"]],
    },
    2: {
        "type": "B777",
        "first_seats": 10, "eco_seats": 300,
        "first_groups": [["A","B"], ["C","D"]],
        "eco_groups":   [["A","B","C"], ["D","E","F"], ["G","H","J"]],
    },
    3: {
        "type": "A350",
        "first_seats": 12, "eco_seats": 250,
        "first_groups": [["A"], ["B","C"], ["D"]],
        "eco_groups":   [["A","B","C"], ["D","E","F"], ["G","H","J"]],
    },
    4: {
        "type": "B787",
        "first_seats": 8, "eco_seats": 220,
        "first_groups": [["A"], ["B","C"], ["D"]],
        "eco_groups":   [["A","B","C"], ["D","E","F"], ["G","H","J"]],
    },
}


def _ac_key(aircraft_id: int) -> int:
    """Mapea el ID real del avión (1-50) a la clave del dict _AIRCRAFT (1-4)."""
    if aircraft_id <= 6:    return 1   # A380
    elif aircraft_id <= 24: return 2   # B777
    elif aircraft_id <= 35: return 3   # A350
    else:                   return 4   # B787


def _seat_list(aircraft_id: int):
    """Devuelve (first_seats[], eco_seats[]) con IDs reales de asiento."""
    cfg = _AIRCRAFT[_ac_key(aircraft_id)]
    first_per_row = sum(len(g) for g in cfg["first_groups"])
    eco_per_row   = sum(len(g) for g in cfg["eco_groups"])
    first_rows    = math.ceil(cfg["first_seats"] / first_per_row)
    eco_rows      = math.ceil(cfg["eco_seats"]   / eco_per_row)

    first = []
    for row in range(1, first_rows + 1):
        for grp in cfg["first_groups"]:
            for col in grp:
                first.append(f"{row}{col}")
    first = first[: cfg["first_seats"]]

    eco = []
    for row in range(first_rows + 1, first_rows + eco_rows + 1):
        for grp in cfg["eco_groups"]:
            for col in grp:
                eco.append(f"{row}{col}")
    eco = eco[: cfg["eco_seats"]]

    return first, eco


# ── Conexiones ─────────────────────────────────────────────────

def _sql_conn(host: str, port: int) -> pyodbc.Connection:
    return pyodbc.connect(
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={host},{port};DATABASE=rpa_db;"
        f"UID=sa;PWD=RPA_StrongPass123!;TrustServerCertificate=yes;"
        "Connection Timeout=30;",
        timeout=30,
    )


def _mongo_conn(host: str, port: int):
    return MongoClient(
        f"mongodb://rpa_admin:RPA_MongoPass123!@{host}:{port}/?authSource=admin",
        serverSelectionTimeoutMS=15_000,
    )["rpa_db"]


# ── ID global thread-safe ─────────────────────────────────────

_id_counter = 1
_id_lock    = threading.Lock()


def _next_id_block(n: int) -> int:
    """Devuelve el inicio de un bloque de n IDs únicos."""
    global _id_counter
    with _id_lock:
        start = _id_counter
        _id_counter += n
    return start


# ── Generación de filas para un vuelo ─────────────────────────

def _build_rows_for_flight(
    flight: dict,
    passport_pool: list[str],
    id_start: int,
    cutoff_72h,          # date: vuelos hasta esta fecha → sin RESERVED
) -> list[tuple]:
    """
    Genera filas de reservación para UN vuelo.

    Regla 72h:
      flight_date <= cutoff_72h → solo CONFIRMED
      flight_date >  cutoff_72h → CONFIRMED + RESERVED
    """
    fid      = flight["id"]
    ac_id    = flight["aircraft_id"]
    p_eco    = float(flight["price_economy"])
    p_first  = float(flight["price_first"])
    node_own = flight["node_owner"]

    # Fecha del vuelo (puede venir como date, str o datetime)
    fd = flight["flight_date"]
    if hasattr(fd, "date"):
        fd = fd.date()
    elif isinstance(fd, str):
        from datetime import date as _date
        fd = _date.fromisoformat(fd[:10])

    allow_reserved = fd > cutoff_72h

    first_seats, eco_seats = _seat_list(ac_id)
    pool_len = len(passport_pool)
    vec = '{"beijing":1,"ukraine":1,"lapaz":1}'

    n_first_conf = math.floor(len(first_seats) * PCT_CONFIRMED)
    n_eco_conf   = math.floor(len(eco_seats)   * PCT_CONFIRMED)
    n_first_res  = math.floor(len(first_seats) * PCT_RESERVED) if allow_reserved else 0
    n_eco_res    = math.floor(len(eco_seats)   * PCT_RESERVED) if allow_reserved else 0

    # Selección aleatoria de asientos
    sel_first = random.sample(first_seats, min(n_first_conf + n_first_res, len(first_seats)))
    conf_first = sel_first[:n_first_conf]
    res_first  = sel_first[n_first_conf:]

    sel_eco = random.sample(eco_seats, min(n_eco_conf + n_eco_res, len(eco_seats)))
    conf_eco = sel_eco[:n_eco_conf]
    res_eco  = sel_eco[n_eco_conf:]

    rows: list[tuple] = []

    def add(seat: str, cabin: str, status: str, price: float) -> None:
        rid = id_start + len(rows)
        # Cada asiento recibe un pasajero distinto rotando el pool
        pax = passport_pool[rid % pool_len]
        txn = f"FILL-{uuid.uuid4().hex[:12].upper()}"
        rows.append((rid, txn, fid, pax, seat, cabin, status, price, node_own, vec))

    for s in conf_first: add(s, "FIRST",   "CONFIRMED", p_first)
    for s in res_first:  add(s, "FIRST",   "RESERVED",  p_first)
    for s in conf_eco:   add(s, "ECONOMY", "CONFIRMED", p_eco)
    for s in res_eco:    add(s, "ECONOMY", "RESERVED",  p_eco)

    return rows


# ── Escritura paralela a los 3 nodos ──────────────────────────

_SQL_INSERT = """
    INSERT INTO dbo.reservations
      (id, transaction_id, flight_id, passenger_passport,
       seat_number, cabin_class, status, price_paid,
       node_origin, vector_clock)
    VALUES (?,?,?,?,?,?,?,?,?,?)
"""

_KEYS = ["id","transaction_id","flight_id","passenger_passport",
         "seat_number","cabin_class","status","price_paid",
         "node_origin","vector_clock"]


def _insert_sql(host: int, port: int, rows: list[tuple], errors: dict) -> None:
    try:
        conn = _sql_conn(host, port)
        conn.autocommit = False
        cur = conn.cursor()
        cur.fast_executemany = True
        cur.executemany(_SQL_INSERT, rows)
        conn.commit()
        conn.close()
    except Exception as e:
        errors[f"{host}:{port}"] = str(e)


def _insert_mongo(host: str, port: int, docs: list[dict], errors: dict) -> None:
    try:
        db = _mongo_conn(host, port)
        ops = [InsertOne(d) for d in docs]
        if ops:
            db.reservations.bulk_write(ops, ordered=False)
    except BulkWriteError as bwe:
        # Registra pero no aborta — puede haber duplicados en re-runs
        log.warning(f"[mongo] BulkWriteError: {bwe.details.get('nInserted',0)} insertados")
    except Exception as e:
        errors[f"mongo:{host}:{port}"] = str(e)


def _write_batch(
    all_sql_rows: list[tuple],
    bej_host: str, bej_port: int,
    ukr_host: str, ukr_port: int,
    mongo_host: str, mongo_port: int,
) -> dict:
    """Escribe un batch a los 3 nodos en paralelo. Retorna errores."""
    mongo_docs = [dict(zip(_KEYS, r)) for r in all_sql_rows]
    errors: dict = {}

    threads = [
        threading.Thread(target=_insert_sql,   args=(bej_host, bej_port, all_sql_rows, errors)),
        threading.Thread(target=_insert_sql,   args=(ukr_host, ukr_port, all_sql_rows, errors)),
        threading.Thread(target=_insert_mongo, args=(mongo_host, mongo_port, mongo_docs, errors)),
    ]
    for t in threads: t.start()
    for t in threads: t.join()
    return errors


# ── Actualizar available_* en flights (SQL) ────────────────────

def _update_available_sql(host: str, port: int) -> None:
    sql_eco = """
        UPDATE f SET f.available_economy =
          CASE
            WHEN f.aircraft_id <= 6  THEN 439
            WHEN f.aircraft_id <= 24 THEN 300
            WHEN f.aircraft_id <= 35 THEN 250
            ELSE 220
          END - ISNULL((
            SELECT COUNT(*) FROM dbo.reservations r
            WHERE r.flight_id = f.id
              AND r.cabin_class = 'ECONOMY'
              AND r.status IN ('CONFIRMED','RESERVED')
          ), 0)
        FROM dbo.flights f
    """
    sql_first = """
        UPDATE f SET f.available_first =
          CASE
            WHEN f.aircraft_id <= 6  THEN 10
            WHEN f.aircraft_id <= 24 THEN 10
            WHEN f.aircraft_id <= 35 THEN 12
            ELSE 8
          END - ISNULL((
            SELECT COUNT(*) FROM dbo.reservations r
            WHERE r.flight_id = f.id
              AND r.cabin_class = 'FIRST'
              AND r.status IN ('CONFIRMED','RESERVED')
          ), 0)
        FROM dbo.flights f
    """
    try:
        conn = _sql_conn(host, port)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql_eco)
        cur.execute(sql_first)
        conn.close()
        log.info(f"[{host}] available_* actualizado")
    except Exception as e:
        log.warning(f"[{host}] error available_*: {e}")


def _update_available_mongo(host: str, port: int) -> None:
    """Recalcula available_* en MongoDB usando aggregation."""
    try:
        db = _mongo_conn(host, port)
        pipeline = [
            {"$match": {"status": {"$in": ["CONFIRMED","RESERVED"]}}},
            {"$group": {
                "_id": {"flight_id": "$flight_id", "cabin": "$cabin_class"},
                "cnt": {"$sum": 1},
            }},
        ]
        counts: dict[int, dict] = {}  # {flight_id: {eco: n, first: n}}
        for doc in db.reservations.aggregate(pipeline):
            fid    = doc["_id"]["flight_id"]
            cabin  = doc["_id"]["cabin"]
            cnt    = doc["cnt"]
            if fid not in counts:
                counts[fid] = {"ECONOMY": 0, "FIRST": 0}
            counts[fid][cabin] = cnt

        _CAPS = {1: (439,10), 2: (300,10), 3: (250,12), 4: (220,8)}  # (eco, first) by _ac_key

        # Actualizar en bulk
        from pymongo import UpdateOne
        ops = []
        for fid, c in counts.items():
            flight = db.flights.find_one({"id": fid}, {"aircraft_id": 1})
            if not flight:
                continue
            cap_eco, cap_first = _CAPS[_ac_key(flight["aircraft_id"])]
            ops.append(UpdateOne(
                {"id": fid},
                {"$set": {
                    "available_economy": max(0, cap_eco   - c.get("ECONOMY", 0)),
                    "available_first":   max(0, cap_first - c.get("FIRST",   0)),
                }},
            ))
            if len(ops) >= 1000:
                db.flights.bulk_write(ops, ordered=False)
                ops = []
        if ops:
            db.flights.bulk_write(ops, ordered=False)
        log.info("[lapaz] available_* actualizado en MongoDB")
    except Exception as e:
        log.warning(f"[lapaz] error available_*: {e}")


# ── Pool de pasaportes ─────────────────────────────────────────

def _load_passport_pool(host: str, port: int, size: int = 100_000) -> list[str]:
    conn = _sql_conn(host, port)
    cur  = conn.cursor()
    cur.execute(f"SELECT TOP {size} passport FROM dbo.passengers ORDER BY NEWID()")
    pool = [r[0] for r in cur.fetchall()]
    conn.close()
    log.info(f"Pool de pasaportes: {len(pool):,} cargados")
    return pool


# ── Carga de vuelos desde la DB ────────────────────────────────

def _load_flights(host: str, port: int) -> list[dict]:
    conn = _sql_conn(host, port)
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, aircraft_id, price_economy, price_first,
               node_owner, flight_date
        FROM dbo.flights
        ORDER BY id
    """)
    cols   = [c[0] for c in cur.description]
    rows   = [dict(zip(cols, r)) for r in cur.fetchall()]
    conn.close()
    return rows


# ── Reset reservaciones ────────────────────────────────────────

def _reset_reservations(
    bej_host: str, bej_port: int,
    ukr_host: str, ukr_port: int,
    mongo_host: str, mongo_port: int,
) -> None:
    log.info("Borrando reservaciones existentes en los 3 nodos...")
    errors: dict = {}

    def del_sql(host, port):
        try:
            conn = _sql_conn(host, port)
            conn.autocommit = True
            conn.cursor().execute("DELETE FROM dbo.reservations")
            conn.close()
        except Exception as e:
            errors[f"{host}:{port}"] = str(e)

    def del_mongo(host, port):
        try:
            db = _mongo_conn(host, port)
            db.reservations.delete_many({})
        except Exception as e:
            errors[f"mongo"] = str(e)

    threads = [
        threading.Thread(target=del_sql,   args=(bej_host, bej_port)),
        threading.Thread(target=del_sql,   args=(ukr_host, ukr_port)),
        threading.Thread(target=del_mongo, args=(mongo_host, mongo_port)),
    ]
    for t in threads: t.start()
    for t in threads: t.join()

    if errors:
        log.warning(f"Errores en reset: {errors}")
    else:
        log.info("Reset completado.")


# ── Stats de carga ─────────────────────────────────────────────

def _print_stats(flights: list[dict], cutoff_72h) -> None:
    from datetime import date as _date

    n_past, n_within72, n_future = 0, 0, 0
    total_conf = total_res = 0

    _CAPS = {1:(439,10), 2:(300,10), 3:(250,12), 4:(220,8)}

    for f in flights:
        fd = f["flight_date"]
        if hasattr(fd, "date"): fd = fd.date()
        elif isinstance(fd, str): fd = _date.fromisoformat(fd[:10])

        eco, first = _CAPS[_ac_key(f["aircraft_id"])]
        total_seats = eco + first

        if fd > cutoff_72h:
            n_future += 1
            total_conf += math.floor(total_seats * PCT_CONFIRMED)
            total_res  += math.floor(total_seats * PCT_RESERVED)
        elif fd < _date.today():
            n_past += 1
            total_conf += math.floor(total_seats * PCT_CONFIRMED)
        else:
            n_within72 += 1
            total_conf += math.floor(total_seats * PCT_CONFIRMED)

    log.info("─" * 60)
    log.info("  Vuelos pasados (solo CONFIRMED):       %8d", n_past)
    log.info("  Vuelos en próx. 72h (solo CONFIRMED):  %8d", n_within72)
    log.info("  Vuelos futuros >72h (CONF + RESERVED): %8d", n_future)
    log.info("  ─")
    log.info("  Reservas CONFIRMED esperadas:  ~%10d", total_conf)
    log.info("  Reservas RESERVED esperadas:   ~%10d", total_res)
    log.info("  TOTAL reservas por nodo:        ~%10d", total_conf + total_res)
    log.info("─" * 60)


# ── Main ───────────────────────────────────────────────────────

def main() -> None:
    global _id_counter

    parser = argparse.ArgumentParser(description="fill_reservations v3")
    parser.add_argument("--reset",   action="store_true", help="Borrar reservas previas antes de llenar")
    parser.add_argument("--local",   action="store_true", help="Usar localhost (fuera del contenedor)")
    parser.add_argument("--dry-run", action="store_true", help="Solo muestra stats, no inserta nada")
    args = parser.parse_args()

    if args.local:
        bej_host, bej_port     = "localhost", 1433
        ukr_host, ukr_port     = "localhost", 1434
        mongo_host, mongo_port = "localhost", 27017
    else:
        bej_host, bej_port     = "sqlserver_beijing",  1433
        ukr_host, ukr_port     = "sqlserver_ukraine",  1433
        mongo_host, mongo_port = "mongodb_lapaz",      27017

    # ── Corte 72 horas ────────────────────────────────────────
    now_utc    = datetime.now(timezone.utc)
    cutoff_72h = (now_utc + timedelta(hours=72)).date()
    log.info("Corte 72h: vuelos con salida > %s admiten RESERVED", cutoff_72h)

    # ── Cargar vuelos ─────────────────────────────────────────
    log.info("Cargando vuelos desde Beijing...")
    flights = _load_flights(bej_host, bej_port)
    log.info("Vuelos a procesar: %d", len(flights))

    # ── Estadísticas estimadas ────────────────────────────────
    _print_stats(flights, cutoff_72h)

    if args.dry_run:
        log.info("Modo dry-run: sin escrituras.")
        return

    # ── Reset si se pide ──────────────────────────────────────
    if args.reset:
        _reset_reservations(bej_host, bej_port, ukr_host, ukr_port, mongo_host, mongo_port)

    # ── Pool de pasaportes ────────────────────────────────────
    passport_pool = _load_passport_pool(bej_host, bej_port, size=100_000)
    if not passport_pool:
        log.error("Sin pasajeros en la DB. Ejecuta parallel_loader primero.")
        sys.exit(1)

    # ── ID base: continúa desde el máximo actual ───────────────
    conn_id = _sql_conn(bej_host, bej_port)
    cur_id  = conn_id.cursor()
    cur_id.execute("SELECT ISNULL(MAX(id),0) FROM dbo.reservations")
    _id_counter = cur_id.fetchone()[0] + 1
    conn_id.close()
    log.info("ID base para esta carga: %d", _id_counter)

    # ── Procesamiento por lotes ───────────────────────────────
    t0             = time.time()
    total_inserted = 0
    n_batches      = math.ceil(len(flights) / BATCH_FLIGHTS)

    for bi in range(n_batches):
        batch = flights[bi * BATCH_FLIGHTS : (bi + 1) * BATCH_FLIGHTS]

        # Construir filas con IDs secuenciales por batch
        # Reservamos un bloque grande para todo el batch y lo usamos localmente
        _CAPS = {1:(439,10), 2:(300,10), 3:(250,12), 4:(220,8)}
        max_seats_batch = sum(
            sum(_CAPS[_ac_key(f["aircraft_id"])]) for f in batch
        )
        batch_id_start = _next_id_block(max_seats_batch)

        all_rows: list[tuple] = []
        local_offset = 0
        for fl in batch:
            rows = _build_rows_for_flight(
                fl, passport_pool, batch_id_start + local_offset, cutoff_72h
            )
            local_offset += len(rows)
            all_rows.extend(rows)

        if not all_rows:
            continue

        errors = _write_batch(
            all_rows,
            bej_host, bej_port,
            ukr_host, ukr_port,
            mongo_host, mongo_port,
        )

        total_inserted += len(all_rows)
        elapsed = time.time() - t0

        if errors:
            log.warning("batch %d/%d errores: %s", bi+1, n_batches, errors)
        else:
            log.info("batch %d/%d → +%d reservas  total=%d  %.0fs",
                     bi+1, n_batches, len(all_rows), total_inserted, elapsed)

    log.info("Reservas insertadas: %d en %.0fs", total_inserted, time.time()-t0)

    # ── Actualizar asientos disponibles ───────────────────────
    log.info("Actualizando available_* en los 3 nodos...")
    threads = [
        threading.Thread(target=_update_available_sql,   args=(bej_host, bej_port)),
        threading.Thread(target=_update_available_sql,   args=(ukr_host, ukr_port)),
        threading.Thread(target=_update_available_mongo, args=(mongo_host, mongo_port)),
    ]
    for t in threads: t.start()
    for t in threads: t.join()

    log.info("=== fill_reservations v3 completado ===")


if __name__ == "__main__":
    main()
