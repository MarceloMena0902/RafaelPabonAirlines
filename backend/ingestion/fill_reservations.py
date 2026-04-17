"""
ingestion/fill_reservations.py
──────────────────────────────────────────────────────────────────
Pre-llena la tabla reservations con:
  • 73 % de asientos → CONFIRMED
  •  3 % de asientos → RESERVED
  • Resto            → disponible para el frontend

Escribe a los 3 nodos en paralelo (SQL Beijing, SQL Ukraine, MongoDB).

Uso (dentro del contenedor rpa_backend):
  python -m ingestion.fill_reservations
  python -m ingestion.fill_reservations --reset   # borra reservas previas
  python -m ingestion.fill_reservations --local   # apunta a localhost
"""
import argparse
import logging
import math
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pyodbc
from pymongo import MongoClient, InsertOne

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
PCT_RESERVED  = 0.03

# ── Batch de vuelos procesados por iteración ──────────────────
BATCH_FLIGHTS = 500

# ── Distribuciones de cabina (igual que SeatMap.jsx) ──────────
_AIRCRAFT = {
    1: {
        "type": "A380", "first_seats": 10, "eco_seats": 439,
        "first_groups": [["A","B"],["C","D"]],
        "eco_groups":   [["A","B","C"],["D","E","F","G"],["H","J","K"]],
    },
    2: {
        "type": "B777", "first_seats": 10, "eco_seats": 300,
        "first_groups": [["A","B"],["C","D"]],
        "eco_groups":   [["A","B","C"],["D","E","F"],["G","H","J"]],
    },
    3: {
        "type": "A350", "first_seats": 12, "eco_seats": 250,
        "first_groups": [["A"],["B","C"],["D"]],
        "eco_groups":   [["A","B","C"],["D","E","F"],["G","H","J"]],
    },
    4: {
        "type": "B787", "first_seats": 8, "eco_seats": 220,
        "first_groups": [["A"],["B","C"],["D"]],
        "eco_groups":   [["A","B","C"],["D","E","F"],["G","H","J"]],
    },
}

def _seat_list(aircraft_id: int):
    """Devuelve (first_seats[], eco_seats[]) con los IDs de asiento reales."""
    cfg = _AIRCRAFT[(aircraft_id - 1) % 4 + 1]
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


def _sql_conn(host: str, port: int):
    return pyodbc.connect(
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={host},{port};DATABASE=rpa_db;"
        f"UID=sa;PWD=RPA_StrongPass123!;TrustServerCertificate=yes",
        timeout=30,
    )


def _mongo_conn(host: str, port: int):
    return MongoClient(
        f"mongodb://rpa_admin:RPA_MongoPass123!@{host}:{port}/?authSource=admin",
        serverSelectionTimeoutMS=10_000,
    )["rpa_db"]


# ── Inserción bulk por nodo ────────────────────────────────────

def _insert_sql(host, port, rows, errors):
    """rows: list of tuples matching INSERT column order."""
    try:
        conn = _sql_conn(host, port)
        conn.autocommit = False
        cur = conn.cursor()
        cur.fast_executemany = True
        sql = """
            INSERT INTO dbo.reservations
              (id, transaction_id, flight_id, passenger_passport,
               seat_number, cabin_class, status, price_paid,
               node_origin, vector_clock)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """
        cur.executemany(sql, rows)
        conn.commit()
        conn.close()
    except Exception as e:
        errors[f"{host}:{port}"] = str(e)


def _insert_mongo(host, port, docs, errors):
    try:
        db = _mongo_conn(host, port)
        ops = [InsertOne(d) for d in docs]
        if ops:
            db.reservations.bulk_write(ops, ordered=False)
    except Exception as e:
        errors[f"mongo:{host}:{port}"] = str(e)


# ── Carga de pool de pasaportes ───────────────────────────────

def _load_passport_pool(host, port, size=60_000):
    conn = _sql_conn(host, port)
    cur  = conn.cursor()
    cur.execute(f"SELECT TOP {size} passport FROM dbo.passengers ORDER BY NEWID()")
    pool = [r[0] for r in cur.fetchall()]
    conn.close()
    log.info(f"Pool de pasaportes: {len(pool):,} cargados desde {host}")
    return pool


# ── Generación de reservaciones para un lote de vuelos ───────

_id_counter = 0
_id_lock    = threading.Lock()

def _next_ids(n: int) -> range:
    global _id_counter
    with _id_lock:
        start = _id_counter
        _id_counter += n
    return range(start, start + n)


def _build_rows_for_flight(flight, passport_pool, id_start):
    """Genera filas de reservación para un vuelo dado."""
    import random

    fid      = flight["id"]
    ac_id    = flight["aircraft_id"]
    p_eco    = float(flight["price_economy"])
    p_first  = float(flight["price_first"])
    node_own = flight["node_owner"]

    first_seats, eco_seats = _seat_list(ac_id)

    n_first_conf = math.floor(len(first_seats) * PCT_CONFIRMED)
    n_first_res  = math.floor(len(first_seats) * PCT_RESERVED)
    n_eco_conf   = math.floor(len(eco_seats)   * PCT_CONFIRMED)
    n_eco_res    = math.floor(len(eco_seats)   * PCT_RESERVED)

    selected_first = random.sample(first_seats, min(n_first_conf + n_first_res, len(first_seats)))
    conf_first = selected_first[:n_first_conf]
    res_first  = selected_first[n_first_conf:]

    selected_eco = random.sample(eco_seats, min(n_eco_conf + n_eco_res, len(eco_seats)))
    conf_eco = selected_eco[:n_eco_conf]
    res_eco  = selected_eco[n_eco_conf:]

    rows = []
    pool_len = len(passport_pool)
    vec = '{"beijing":1,"ukraine":1,"lapaz":1}'

    def add(seat, cabin, status, price):
        pax = passport_pool[id_start % pool_len]  # wrap-around
        txn = f"FILL-{uuid.uuid4().hex[:12].upper()}"
        rows.append((id_start + len(rows), txn, fid, pax, seat, cabin, status, price, node_own, vec))

    for s in conf_first: add(s, "FIRST",   "CONFIRMED", p_first)
    for s in res_first:  add(s, "FIRST",   "RESERVED",  p_first)
    for s in conf_eco:   add(s, "ECONOMY", "CONFIRMED", p_eco)
    for s in res_eco:    add(s, "ECONOMY", "RESERVED",  p_eco)

    return rows


def _process_batch(flights_batch, passport_pool, id_offset,
                   bej_host, bej_port, ukr_host, ukr_port,
                   mongo_host, mongo_port):
    all_sql_rows  = []
    all_mongo_docs = []

    for fl in flights_batch:
        rows = _build_rows_for_flight(fl, passport_pool, id_offset + len(all_sql_rows))
        all_sql_rows.extend(rows)

    # Convertir a documentos Mongo
    keys = ["id","transaction_id","flight_id","passenger_passport",
            "seat_number","cabin_class","status","price_paid",
            "node_origin","vector_clock"]
    for r in all_sql_rows:
        all_mongo_docs.append(dict(zip(keys, r)))

    errors = {}
    threads = [
        threading.Thread(target=_insert_sql,   args=(bej_host,   bej_port,   all_sql_rows,   errors)),
        threading.Thread(target=_insert_sql,   args=(ukr_host,   ukr_port,   all_sql_rows,   errors)),
        threading.Thread(target=_insert_mongo, args=(mongo_host, mongo_port, all_mongo_docs, errors)),
    ]
    for t in threads: t.start()
    for t in threads: t.join()

    return len(all_sql_rows), errors


# ── Reset reservaciones ───────────────────────────────────────

def _reset_reservations(bej_host, bej_port, ukr_host, ukr_port, mongo_host, mongo_port):
    log.info("Eliminando reservaciones existentes en los 3 nodos...")
    errors = {}

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
            errors[f"mongo:{host}:{port}"] = str(e)

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


# ── Actualizar columnas available_* en flights ────────────────

def _update_available_seats(bej_host, bej_port, ukr_host, ukr_port):
    """
    Recalcula available_economy / available_first restando
    las reservaciones CONFIRMED+RESERVED ya insertadas.
    """
    sql = """
        UPDATE f
        SET
          f.available_economy = (
            SELECT COUNT(*) FROM dbo.reservations r
            WHERE r.flight_id = f.id AND r.cabin_class='ECONOMY'
              AND r.status IN ('CONFIRMED','RESERVED')
          ),
          f.available_first = (
            SELECT COUNT(*) FROM dbo.reservations r
            WHERE r.flight_id = f.id AND r.cabin_class='FIRST'
              AND r.status IN ('CONFIRMED','RESERVED')
          )
        FROM dbo.flights f
    """
    # Reusamos para mostrar disponibles = total - vendidos
    sql2_eco = """
        UPDATE f
        SET f.available_economy = ac.eco - ISNULL(r.cnt,0)
        FROM dbo.flights f
        JOIN (VALUES (1,439),(2,300),(3,250),(4,220)) AS ac(id,eco)
          ON f.aircraft_id = ac.id
        LEFT JOIN (
            SELECT flight_id, COUNT(*) AS cnt
            FROM dbo.reservations
            WHERE cabin_class='ECONOMY' AND status IN ('CONFIRMED','RESERVED')
            GROUP BY flight_id
        ) r ON r.flight_id = f.id
    """
    sql2_first = """
        UPDATE f
        SET f.available_first = ac.fc - ISNULL(r.cnt,0)
        FROM dbo.flights f
        JOIN (VALUES (1,10),(2,10),(3,12),(4,8)) AS ac(id,fc)
          ON f.aircraft_id = ac.id
        LEFT JOIN (
            SELECT flight_id, COUNT(*) AS cnt
            FROM dbo.reservations
            WHERE cabin_class='FIRST' AND status IN ('CONFIRMED','RESERVED')
            GROUP BY flight_id
        ) r ON r.flight_id = f.id
    """
    for host, port in [(bej_host, bej_port), (ukr_host, ukr_port)]:
        try:
            conn = _sql_conn(host, port)
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute(sql2_eco)
            cur.execute(sql2_first)
            conn.close()
            log.info(f"[{host}] available_* actualizado")
        except Exception as e:
            log.warning(f"[{host}] error actualizando available: {e}")


# ── Main ───────────────────────────────────────────────────────

def main():
    global _id_counter

    parser = argparse.ArgumentParser()
    parser.add_argument("--reset",  action="store_true", help="Borrar reservas previas")
    parser.add_argument("--local",  action="store_true", help="Usar localhost (fuera del contenedor)")
    args = parser.parse_args()

    if args.local:
        bej_host, bej_port   = "localhost", 1433
        ukr_host, ukr_port   = "localhost", 1434
        mongo_host, mongo_port = "localhost", 27017
    else:
        bej_host, bej_port   = "sqlserver_beijing",  1433
        ukr_host, ukr_port   = "sqlserver_ukraine",  1433
        mongo_host, mongo_port = "mongodb_lapaz",    27017

    if args.reset:
        _reset_reservations(bej_host, bej_port, ukr_host, ukr_port, mongo_host, mongo_port)

    # Cargar pool de pasaportes
    passport_pool = _load_passport_pool(bej_host, bej_port, size=50_000)
    if not passport_pool:
        log.error("No se encontraron pasajeros. Ejecuta el loader primero.")
        sys.exit(1)

    # Obtener todos los vuelos
    conn   = _sql_conn(bej_host, bej_port)
    cur    = conn.cursor()
    cur.execute("SELECT id, aircraft_id, price_economy, price_first, node_owner FROM dbo.flights ORDER BY id")
    flights = [{"id": r[0], "aircraft_id": r[1], "price_economy": r[2],
                "price_first": r[3], "node_owner": r[4]} for r in cur.fetchall()]
    conn.close()
    log.info(f"Vuelos a procesar: {len(flights):,}")

    # Obtener max id existente para no colisionar
    conn2 = _sql_conn(bej_host, bej_port)
    cur2  = conn2.cursor()
    cur2.execute("SELECT ISNULL(MAX(id),0) FROM dbo.reservations")
    _id_counter = cur2.fetchone()[0] + 1
    conn2.close()
    log.info(f"ID base: {_id_counter}")

    t0             = time.time()
    total_inserted = 0
    n_batches      = math.ceil(len(flights) / BATCH_FLIGHTS)

    for bi in range(n_batches):
        batch = flights[bi * BATCH_FLIGHTS : (bi + 1) * BATCH_FLIGHTS]
        id_off = _id_counter

        inserted, errors = _process_batch(
            batch, passport_pool, id_off,
            bej_host, bej_port, ukr_host, ukr_port, mongo_host, mongo_port,
        )

        _id_counter += inserted
        total_inserted += inserted

        if errors:
            log.warning(f"batch {bi+1}/{n_batches} errores: {errors}")
        else:
            elapsed = time.time() - t0
            log.info(f"batch {bi+1}/{n_batches} → +{inserted:,} reservas  total={total_inserted:,}  {elapsed:.0f}s")

    log.info(f"Reservas insertadas: {total_inserted:,} en {time.time()-t0:.0f}s")
    log.info("Actualizando asientos disponibles en vuelos...")
    _update_available_seats(bej_host, bej_port, ukr_host, ukr_port)
    log.info("=== fill_reservations completado ===")


if __name__ == "__main__":
    main()
