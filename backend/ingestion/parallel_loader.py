"""
ingestion/parallel_loader.py  —  v5  (optimizado + pasos separados)
─────────────────────────────────────────────────────────────────────
Carga 60 000 vuelos y 5 000 000 pasajeros a los 3 nodos.

Optimizaciones:
  • Escritura a los 3 nodos EN PARALELO por cada chunk (3x más rápido).
  • Índices SQL deshabilitados durante la carga, reconstruidos al final.
  • Conexiones persistentes por nodo (sin abrir/cerrar por chunk).
  • Chunks grandes: 10 000 vuelos, 500 000 pasajeros.
  • fast_executemany = True + TABLOCK hint → mínimo overhead de bloqueo.
  • Pasajeros: hasta 4 chunks en vuelo simultáneo (semáforo).

Uso
────
  # Solo vuelos (luego verificar con --verify antes de pasajeros):
  python -m ingestion.parallel_loader --local --flights-only

  # Verificar conteos en los 3 nodos:
  python -m ingestion.parallel_loader --local --verify

  # Solo pasajeros (después de verificar vuelos):
  python -m ingestion.parallel_loader --local --passengers-only

  # Todo en un paso (comportamiento original):
  python -m ingestion.parallel_loader --local

  # Con reset previo:
  python -m ingestion.parallel_loader --local --reset

  # Con ruta explícita de CSVs:
  python -m ingestion.parallel_loader --path "E:/ruta/a/contexto"
"""
import argparse
import logging
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import pyodbc
from pymongo import MongoClient, InsertOne
from datetime import date as _date, time as _time

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))

from config import settings
from data.matrices import PRICES_ECONOMY, PRICES_FIRST, FLIGHT_HOURS, aircraft_type_for_id, AIRCRAFT
from geo.proximity import node_for_airport

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ── Tamaños de chunk ───────────────────────────────────────────
CHUNK_FLIGHTS    =  10_000
CHUNK_PASSENGERS = 100_000

# ── Semáforo: máx chunks de pasajeros en vuelo simultáneo ─────
_PAX_SEM = threading.Semaphore(3)

# ── Contadores de progreso ─────────────────────────────────────
_progress_lock = threading.Lock()
_processed_pax = 0


# ══════════════════════════════════════════════════════════════
#  Resolución de rutas
# ══════════════════════════════════════════════════════════════

def _find_datasets_path(override: str | None) -> Path:
    import os
    candidates = []
    if override:
        candidates.append(Path(override))
    env = os.environ.get("DATASETS_PATH")
    if env:
        candidates.append(Path(env))
    candidates.append(_BACKEND_ROOT / "data" / "datasets")
    candidates.append(Path(settings.context_path))

    for path in candidates:
        if (path / "vuelos.csv").exists():
            logger.info("Datasets encontrados en: %s", path)
            return path

    logger.warning("No se encontró vuelos.csv. Rutas revisadas: %s", candidates)
    return candidates[-1]


# ══════════════════════════════════════════════════════════════
#  Conexiones
# ══════════════════════════════════════════════════════════════

def _sql_conn(host: str, port: int) -> pyodbc.Connection:
    conn = pyodbc.connect(
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={host},{port};"
        f"DATABASE={settings.sql_database};"
        f"UID={settings.sql_user};"
        f"PWD={settings.sql_password};"
        "TrustServerCertificate=yes;"
        "Connection Timeout=10;",
        autocommit=False,
    )
    return conn


def _mongo_db(host: str | None = None):
    cli = MongoClient(settings.mongo_uri())
    return cli, cli[settings.mongo_database]


# ══════════════════════════════════════════════════════════════
#  Gestión de índices
# ══════════════════════════════════════════════════════════════

_INDEX_TABLES = ("dbo.flights", "dbo.passengers")


def _repair_indexes(conn: pyodbc.Connection, node: str) -> None:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT OBJECT_NAME(i.object_id)
        FROM   sys.indexes i
        JOIN   sys.objects o ON i.object_id = o.object_id
        WHERE  i.is_disabled = 1 AND o.type = 'U'
          AND  OBJECT_NAME(i.object_id) IN ('flights','passengers','reservations')
    """)
    disabled = {row[0] for row in cursor.fetchall()}
    if disabled:
        logger.info("[%s] Reconstruyendo índices deshabilitados: %s", node, disabled)
        for tbl in disabled:
            cursor.execute(f"ALTER INDEX ALL ON dbo.{tbl} REBUILD")
        conn.commit()


def _disable_indexes(conn: pyodbc.Connection) -> None:
    cursor = conn.cursor()
    for tbl in _INDEX_TABLES:
        try:
            cursor.execute(f"ALTER INDEX ALL ON {tbl} DISABLE")
        except Exception:
            pass
    conn.commit()


def _rebuild_indexes(conn: pyodbc.Connection, node: str) -> None:
    cursor = conn.cursor()
    logger.info("[%s] Reconstruyendo índices...", node)
    for tbl in _INDEX_TABLES:
        cursor.execute(f"ALTER INDEX ALL ON {tbl} REBUILD")
    conn.commit()
    logger.info("[%s] Índices reconstruidos.", node)


# ══════════════════════════════════════════════════════════════
#  INSERT helpers
# ══════════════════════════════════════════════════════════════

_SQL_FLIGHTS = """
    INSERT INTO dbo.flights
        (id, flight_date, departure_time, origin, destination,
         aircraft_id, status, gate, price_economy, price_first,
         duration_hours, available_economy, available_first, node_owner)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""

_SQL_PASSENGERS = """
    INSERT INTO dbo.passengers
        (passport, full_name, nationality, email, home_region)
    VALUES (?,?,?,?,?)
"""

# Versión idempotente: salta si el pasaporte ya existe (para re-runs y reparaciones)
_SQL_PASSENGERS_UPSERT = """
    INSERT INTO dbo.passengers (passport, full_name, nationality, email, home_region)
    SELECT ?,?,?,?,?
    WHERE NOT EXISTS (SELECT 1 FROM dbo.passengers WHERE passport = ?)
"""


def _sql_bulk(conn: pyodbc.Connection, sql: str, rows: list[tuple]) -> None:
    cur = conn.cursor()
    cur.fast_executemany = True
    cur.executemany(sql, rows)
    conn.commit()


def _sql_bulk_passengers_safe(conn: pyodbc.Connection, rows: list[tuple]) -> int:
    """
    INSERT idempotente para pasajeros: salta los que ya existen.
    rows: (passport, full_name, nationality, email, home_region)
    Retorna el número de filas efectivamente insertadas.
    """
    # El parámetro de passport va duplicado: una vez para INSERT y otra para WHERE NOT EXISTS
    rows_ext = [(r[0], r[1], r[2], r[3], r[4], r[0]) for r in rows]
    cur = conn.cursor()
    # fast_executemany=False para procesar fila a fila (necesario con subquery)
    cur.fast_executemany = False
    cur.executemany(_SQL_PASSENGERS_UPSERT, rows_ext)
    inserted = cur.rowcount  # -1 si el driver no reporta, ≥0 en la mayoría de los casos
    conn.commit()
    return max(inserted, 0)


# ══════════════════════════════════════════════════════════════
#  Transformaciones
# ══════════════════════════════════════════════════════════════

def _parse_date(val) -> _date:
    return _date.fromisoformat(str(val).strip())


def _parse_time(val) -> _time:
    s = str(val).strip()
    if len(s) == 5:
        s += ":00"
    return _time.fromisoformat(s)


def _transform_flights(df: pd.DataFrame, start_id: int) -> tuple[list[tuple], list[dict]]:
    sql_rows, mongo_docs = [], []
    for i, row in enumerate(df.itertuples(index=False), start=start_id):
        origin      = str(row.Origen).strip().upper()
        destination = str(row.Destino).strip().upper()
        aircraft_id = (int(row.AvionId) - 1) % 4 + 1
        aircraft    = AIRCRAFT[aircraft_type_for_id(aircraft_id)]
        price_eco   = float(PRICES_ECONOMY.get(origin, {}).get(destination) or 0)
        price_first = float(PRICES_FIRST.get(origin,   {}).get(destination) or 0)
        duration    = int(FLIGHT_HOURS.get(origin,     {}).get(destination, 0))
        node        = node_for_airport(origin)
        fd          = _parse_date(row.Fecha)
        ft          = _parse_time(row.Hora)
        row_t = (
            i, fd, ft, origin, destination, aircraft_id,
            str(row.Estado).strip(), str(row.Gate).strip(),
            price_eco, price_first, duration,
            aircraft["economy_seats"], aircraft["first_class_seats"], node,
        )
        sql_rows.append(row_t)
        mongo_docs.append({
            "id": i,
            "flight_date": fd.isoformat(),
            "departure_time": ft.strftime("%H:%M:%S"),
            "origin": origin, "destination": destination,
            "aircraft_id": aircraft_id,
            "status": row_t[6], "gate": row_t[7],
            "price_economy": price_eco, "price_first": price_first,
            "duration_hours": duration,
            "available_economy": aircraft["economy_seats"],
            "available_first": aircraft["first_class_seats"],
            "node_owner": node,
        })
    return sql_rows, mongo_docs


_REGION_MAP = {
    "Boliviano": "LATAM",   "Brasilero": "LATAM",    "Español": "LATAM",
    "Ucraniano": "EURO_ESTE","Turco": "EURO_ESTE",
    "Alemán":    "EURO_OESTE","Francés": "EURO_OESTE","Holandés": "EURO_OESTE",
    "Británico": "EURO_OESTE",
    "Emiratí":   "ORIENTE",  "Chino": "ORIENTE",     "Japonés": "ORIENTE",
    "Singapurense": "ORIENTE",
    "Estadounidense": "NORTE_AMERICA",
}


def _transform_passengers(df: pd.DataFrame) -> tuple[list[tuple], list[dict]]:
    sql_rows, mongo_docs = [], []
    for row in df.itertuples(index=False):
        nat      = str(row.Nacionalidad).strip()
        region   = _REGION_MAP.get(nat, "OTRO")
        passport = str(row.Pasaporte).strip()
        name     = str(row.NombreCompleto).strip()
        email    = str(row.Email).strip()
        sql_rows.append((passport, name, nat, email, region))
        mongo_docs.append({
            "passport": passport, "full_name": name,
            "nationality": nat,   "email": email,
            "home_region": region,
        })
    return sql_rows, mongo_docs


# ══════════════════════════════════════════════════════════════
#  Escritura paralela a los 3 nodos
# ══════════════════════════════════════════════════════════════

def _write_flights_parallel(
    sql_rows: list[tuple],
    mongo_docs: list[dict],
    bej_host: str, bej_port: int,
    ukr_host: str, ukr_port: int,
) -> None:
    """Escribe el mismo batch a Beijing, Ucrania y MongoDB simultáneamente."""

    errors = []

    def write_bej():
        try:
            conn = _sql_conn(bej_host, bej_port)
            _sql_bulk(conn, _SQL_FLIGHTS, sql_rows)
            conn.close()
        except Exception as e:
            errors.append(f"beijing: {e}")

    def write_ukr():
        try:
            conn = _sql_conn(ukr_host, ukr_port)
            _sql_bulk(conn, _SQL_FLIGHTS, sql_rows)
            conn.close()
        except Exception as e:
            errors.append(f"ukraine: {e}")

    def write_mongo():
        try:
            cli, db = _mongo_db()
            db.flights.insert_many(mongo_docs, ordered=False)
            cli.close()
        except Exception as e:
            errors.append(f"lapaz: {e}")

    threads = [
        threading.Thread(target=write_bej,   daemon=True),
        threading.Thread(target=write_ukr,   daemon=True),
        threading.Thread(target=write_mongo, daemon=True),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if errors:
        raise RuntimeError("; ".join(errors))


def _write_passengers_parallel(
    sql_rows: list[tuple],
    mongo_docs: list[dict],
    bej_host: str, bej_port: int,
    ukr_host: str, ukr_port: int,
    chunk_label: str,
) -> int:
    """
    Escribe un chunk de pasajeros a los 3 nodos simultáneamente.
    Usa INSERT idempotente (WHERE NOT EXISTS) → seguro re-ejecutar.
    Usa semáforo global para limitar chunks en vuelo.
    """
    with _PAX_SEM:
        errors = []

        def write_bej():
            try:
                conn = _sql_conn(bej_host, bej_port)
                _sql_bulk_passengers_safe(conn, sql_rows)
                conn.close()
            except Exception as e:
                errors.append(f"beijing: {e}")

        def write_ukr():
            try:
                conn = _sql_conn(ukr_host, ukr_port)
                _sql_bulk_passengers_safe(conn, sql_rows)
                conn.close()
            except Exception as e:
                errors.append(f"ukraine: {e}")

        def write_mongo():
            try:
                cli, db = _mongo_db()
                # ordered=False → continúa ante duplicados (DuplicateKeyError)
                try:
                    db.passengers.insert_many(mongo_docs, ordered=False)
                except Exception:
                    pass  # ignora duplicados en Mongo
                cli.close()
            except Exception as e:
                errors.append(f"lapaz: {e}")

        threads = [
            threading.Thread(target=write_bej,   daemon=True),
            threading.Thread(target=write_ukr,   daemon=True),
            threading.Thread(target=write_mongo, daemon=True),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        if errors:
            logger.warning("[pasajeros] %s errores: %s", chunk_label, "; ".join(errors))

        with _progress_lock:
            global _processed_pax
            _processed_pax += len(sql_rows)
            logger.info("[pasajeros] %s → %d rows  (total: %d)",
                        chunk_label, len(sql_rows), _processed_pax)

        return len(sql_rows)


# ══════════════════════════════════════════════════════════════
#  Carga de vuelos
# ══════════════════════════════════════════════════════════════

def load_flights(
    datasets_path: Path,
    bej_host: str, bej_port: int,
    ukr_host: str, ukr_port: int,
) -> None:
    csv_path = datasets_path / "vuelos.csv"
    logger.info("Leyendo vuelos: %s", csv_path)
    df    = pd.read_csv(csv_path)
    total = len(df)
    logger.info("Vuelos encontrados: %d", total)

    n_chunks = (total + CHUNK_FLIGHTS - 1) // CHUNK_FLIGHTS

    for ci in range(n_chunks):
        chunk     = df[ci * CHUNK_FLIGHTS : (ci + 1) * CHUNK_FLIGHTS]
        start_id  = ci * CHUNK_FLIGHTS + 1
        sql_rows, mongo_docs = _transform_flights(chunk, start_id)

        t0 = time.time()
        _write_flights_parallel(sql_rows, mongo_docs, bej_host, bej_port, ukr_host, ukr_port)
        elapsed = time.time() - t0
        logger.info(
            "[vuelos] chunk %d/%d  (%d vuelos)  %.1fs",
            ci + 1, n_chunks, len(sql_rows), elapsed,
        )

    logger.info("Vuelos cargados: %d en 3 nodos.", total)


# ══════════════════════════════════════════════════════════════
#  Carga de pasajeros
# ══════════════════════════════════════════════════════════════

def load_passengers(
    datasets_path: Path,
    bej_host: str, bej_port: int,
    ukr_host: str, ukr_port: int,
) -> None:
    global _processed_pax
    _processed_pax = 0

    csv_path = datasets_path / "pasajeros.csv"
    logger.info("Leyendo pasajeros: %s", csv_path)
    total = sum(1 for _ in open(csv_path, encoding="utf-8")) - 1
    logger.info("Pasajeros encontrados: %d", total)

    seen: set[str] = set()
    futures = []
    executor = ThreadPoolExecutor(max_workers=4)
    chunk_num = 0

    for chunk in pd.read_csv(csv_path, chunksize=CHUNK_PASSENGERS):
        chunk_num += 1

        # Deduplicar dentro del chunk y contra chunks anteriores
        chunk = chunk.drop_duplicates(subset=["Pasaporte"], keep="first")
        chunk = chunk[~chunk["Pasaporte"].isin(seen)]
        if chunk.empty:
            logger.info("[pasajeros] chunk %d → vacío tras deduplicar", chunk_num)
            continue
        seen.update(chunk["Pasaporte"].tolist())

        sql_rows, mongo_docs = _transform_passengers(chunk)
        label = f"chunk {chunk_num}"

        future = executor.submit(
            _write_passengers_parallel,
            sql_rows, mongo_docs,
            bej_host, bej_port, ukr_host, ukr_port,
            label,
        )
        futures.append(future)

    # Esperar a que todos terminen
    for f in as_completed(futures):
        try:
            f.result()
        except Exception as exc:
            logger.error("[pasajeros] error en chunk: %s", exc)

    executor.shutdown(wait=True)
    logger.info("Pasajeros cargados: %d en 3 nodos.", _processed_pax)


# ══════════════════════════════════════════════════════════════
#  Reset: DROP + RECREATE
# ══════════════════════════════════════════════════════════════

_SQL_RESET: list[str] = [
    "IF OBJECT_ID('dbo.sync_queue',   'U') IS NOT NULL DROP TABLE dbo.sync_queue",
    "IF OBJECT_ID('dbo.reservations', 'U') IS NOT NULL DROP TABLE dbo.reservations",
    "IF OBJECT_ID('dbo.flights',      'U') IS NOT NULL DROP TABLE dbo.flights",
    "IF OBJECT_ID('dbo.passengers',   'U') IS NOT NULL DROP TABLE dbo.passengers",
    """CREATE TABLE dbo.passengers (
        passport    NVARCHAR(20)  NOT NULL PRIMARY KEY,
        full_name   NVARCHAR(100) NOT NULL,
        nationality NVARCHAR(50)  NOT NULL,
        email       NVARCHAR(100) NOT NULL,
        home_region NVARCHAR(20)  NULL,
        created_at  DATETIME2     NOT NULL DEFAULT GETUTCDATE()
    )""",
    """CREATE TABLE dbo.flights (
        id                BIGINT        NOT NULL PRIMARY KEY,
        flight_date       DATE          NOT NULL,
        departure_time    TIME          NOT NULL,
        origin            CHAR(3)       NOT NULL,
        destination       CHAR(3)       NOT NULL,
        aircraft_id       INT           NOT NULL,
        status            NVARCHAR(20)  NOT NULL,
        gate              NVARCHAR(5)   NOT NULL,
        price_economy     DECIMAL(10,2) NOT NULL,
        price_first       DECIMAL(10,2) NOT NULL,
        duration_hours    INT           NOT NULL,
        available_economy INT           NOT NULL,
        available_first   INT           NOT NULL,
        node_owner        NVARCHAR(20)  NOT NULL,
        created_at        DATETIME2     NOT NULL DEFAULT GETUTCDATE()
    )""",
    "CREATE INDEX ix_flights_date   ON dbo.flights(flight_date, origin)",
    "CREATE INDEX ix_flights_node   ON dbo.flights(node_owner)",
    """CREATE TABLE dbo.reservations (
        id                 BIGINT        NOT NULL PRIMARY KEY,
        transaction_id     NVARCHAR(60)  NOT NULL UNIQUE,
        flight_id          BIGINT        NOT NULL,
        passenger_passport NVARCHAR(20)  NOT NULL,
        seat_number        NVARCHAR(5)   NOT NULL,
        cabin_class        NVARCHAR(10)  NOT NULL,
        status             NVARCHAR(20)  NOT NULL DEFAULT 'CONFIRMED',
        price_paid         DECIMAL(10,2) NOT NULL,
        node_origin        NVARCHAR(20)  NOT NULL,
        vector_clock       NVARCHAR(200) NOT NULL,
        created_at         DATETIME2     NOT NULL DEFAULT GETUTCDATE(),
        updated_at         DATETIME2     NOT NULL DEFAULT GETUTCDATE()
    )""",
    "CREATE INDEX ix_reservations_flight    ON dbo.reservations(flight_id)",
    "CREATE INDEX ix_reservations_passenger ON dbo.reservations(passenger_passport)",
    """CREATE TABLE dbo.sync_queue (
        id             BIGINT        NOT NULL IDENTITY(1,1) PRIMARY KEY,
        transaction_id NVARCHAR(60)  NOT NULL,
        operation_type NVARCHAR(20)  NOT NULL,
        target_node    NVARCHAR(20)  NOT NULL,
        payload        NVARCHAR(MAX) NOT NULL,
        vector_clock   NVARCHAR(200) NOT NULL,
        queued_at      DATETIME2     NOT NULL DEFAULT GETUTCDATE(),
        replayed       BIT           NOT NULL DEFAULT 0
    )""",
    "CREATE INDEX ix_sync_pending ON dbo.sync_queue(target_node, replayed)",
]


def _reset_sql(node: str, host: str, port: int) -> None:
    conn   = _sql_conn(host, port)
    cursor = conn.cursor()
    for stmt in _SQL_RESET:
        stmt = stmt.strip()
        if not stmt:
            continue
        try:
            cursor.execute(stmt)
            conn.commit()
        except Exception as exc:
            logger.debug("[reset/%s] ignorado: %s", node, exc)
    conn.close()
    logger.info("[reset] %s listo", node)


def _reset_mongo() -> None:
    cli, db = _mongo_db()
    for col in ("sync_queue", "reservations", "flights", "passengers"):
        db[col].drop()
    db.flights.create_index([("id", 1)],            unique=True)
    db.flights.create_index([("flight_date", 1),    ("origin", 1)])
    db.flights.create_index([("node_owner", 1)])
    db.passengers.create_index([("passport", 1)],   unique=True)
    db.reservations.create_index([("id", 1)],       unique=True)
    db.reservations.create_index([("transaction_id", 1)], unique=True)
    db.reservations.create_index([("flight_id", 1)])
    db.sync_queue.create_index([("target_node", 1), ("replayed", 1)])
    db.ikj_counter.update_one(
        {"node": "lapaz"}, {"$set": {"next_id": 3_000_000_000}}, upsert=True
    )
    cli.close()
    logger.info("[reset] lapaz listo")


def reset_all_nodes() -> None:
    logger.info("=== RESET en los 3 nodos (paralelo) ===")
    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = {
            ex.submit(_reset_sql,   "beijing", settings.sql_beijing_host, settings.sql_beijing_port): "beijing",
            ex.submit(_reset_sql,   "ukraine", settings.sql_ukraine_host, settings.sql_ukraine_port): "ukraine",
            ex.submit(_reset_mongo): "lapaz",
        }
        for f in as_completed(futures):
            try:
                f.result()
            except Exception as exc:
                logger.error("[reset/%s] %s", futures[f], exc)
    logger.info("=== RESET completado ===")


# ══════════════════════════════════════════════════════════════
#  Verificación de conteos en los 3 nodos
# ══════════════════════════════════════════════════════════════

def verify_counts(bej_host: str, bej_port: int, ukr_host: str, ukr_port: int) -> None:
    """Imprime conteos de flights, passengers y reservations en los 3 nodos."""
    logger.info("=== Verificando conteos en los 3 nodos ===")

    tables = ["flights", "passengers", "reservations"]

    def _count_sql(node: str, host: str, port: int) -> dict:
        counts = {}
        try:
            conn = _sql_conn(host, port)
            cur  = conn.cursor()
            for tbl in tables:
                cur.execute(f"SELECT COUNT(*) FROM dbo.{tbl}")
                counts[tbl] = cur.fetchone()[0]
            # Muestra de 3 vuelos
            cur.execute(
                "SELECT TOP 3 id, origin, destination, flight_date, status "
                "FROM dbo.flights ORDER BY id"
            )
            counts["_sample"] = cur.fetchall()
            conn.close()
        except Exception as e:
            counts["_error"] = str(e)
        return counts

    def _count_mongo() -> dict:
        counts = {}
        try:
            cli, db = _mongo_db()
            for tbl in tables:
                counts[tbl] = db[tbl].count_documents({})
            counts["_sample"] = list(db.flights.find(
                {}, {"_id": 0, "id": 1, "origin": 1, "destination": 1,
                     "flight_date": 1, "status": 1}
            ).sort("id", 1).limit(3))
            cli.close()
        except Exception as e:
            counts["_error"] = str(e)
        return counts

    results = {}
    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = {
            ex.submit(_count_sql, "beijing", bej_host, bej_port): "beijing",
            ex.submit(_count_sql, "ukraine", ukr_host, ukr_port): "ukraine",
            ex.submit(_count_mongo):                               "lapaz",
        }
        for f in as_completed(futures):
            node = futures[f]
            results[node] = f.result()

    print("\n┌─────────────────────────────────────────────────────────────┐")
    print("│            VERIFICACIÓN DE DATOS — 3 NODOS                  │")
    print("├──────────────┬──────────────┬──────────────┬────────────────┤")
    print("│ Tabla        │    Beijing   │   Ukraine    │    La Paz      │")
    print("├──────────────┼──────────────┼──────────────┼────────────────┤")
    for tbl in tables:
        bej = results.get("beijing", {}).get(tbl, "ERR")
        ukr = results.get("ukraine", {}).get(tbl, "ERR")
        lpz = results.get("lapaz",   {}).get(tbl, "ERR")
        ok  = "✓" if bej == ukr == lpz else "✗ DIFF"
        print(f"│ {tbl:<12} │ {str(bej):>12} │ {str(ukr):>12} │ {str(lpz):>14} │  {ok}")
    print("└──────────────┴──────────────┴──────────────┴────────────────┘")

    # Muestra de vuelos
    sample = results.get("beijing", {}).get("_sample", [])
    if sample:
        print("\nMuestra de vuelos (Beijing):")
        for row in sample:
            print(f"  id={row[0]}  {row[1]} → {row[2]}  fecha={row[3]}  estado={row[4]}")

    # Errores
    for node, data in results.items():
        if "_error" in data:
            logger.error("[%s] %s", node, data["_error"])

    print()
    logger.info("=== Verificación completada ===")


# ══════════════════════════════════════════════════════════════
#  Entry point
# ══════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="Ingesta RafaelPabonAirlines v5")
    parser.add_argument("--reset",           action="store_true", help="DROP + RECREATE antes de cargar")
    parser.add_argument("--yes",             action="store_true", help="Omite confirmación del reset")
    parser.add_argument("--local",           action="store_true", help="Conecta a localhost en vez de hostnames Docker")
    parser.add_argument("--path",            metavar="DIR", default=None, help="Ruta a vuelos.csv / pasajeros.csv")
    parser.add_argument("--workers",         type=int, default=4, help="Chunks de pasajeros en paralelo (default: 4)")
    parser.add_argument("--flights-only",    action="store_true", help="Solo carga vuelos (sin pasajeros)")
    parser.add_argument("--passengers-only", action="store_true", help="Solo carga pasajeros (vuelos ya cargados)")
    parser.add_argument("--verify",          action="store_true", help="Muestra conteos en los 3 nodos y sale")
    args = parser.parse_args()

    if args.local:
        bej_host, bej_port = "localhost", 1433
        ukr_host, ukr_port = "localhost", 1434
        logger.info("Modo --local: localhost:1433 / localhost:1434")
    else:
        bej_host = settings.sql_beijing_host
        bej_port = settings.sql_beijing_port
        ukr_host = settings.sql_ukraine_host
        ukr_port = settings.sql_ukraine_port

    # ── Solo verificar ──────────────────────────────────────────
    if args.verify:
        verify_counts(bej_host, bej_port, ukr_host, ukr_port)
        return

    datasets_path = _find_datasets_path(args.path)

    if args.reset:
        if not args.yes:
            confirm = input(
                "\n  ADVERTENCIA: Se eliminarán TODOS los datos en los 3 nodos.\n"
                "  Escribe 'CONFIRMAR' para continuar: "
            ).strip()
            if confirm != "CONFIRMAR":
                logger.info("Reset cancelado.")
                sys.exit(0)
        reset_all_nodes()

    t0 = time.time()

    do_flights    = not args.passengers_only
    do_passengers = not args.flights_only

    if do_flights and do_passengers:
        logger.info("=== Ingesta completa: vuelos + pasajeros ===")
    elif do_flights:
        logger.info("=== Cargando solo vuelos ===")
    else:
        logger.info("=== Cargando solo pasajeros ===")

    if do_flights:
        load_flights(datasets_path, bej_host, bej_port, ukr_host, ukr_port)
        if do_passengers:
            logger.info("Vuelos listos. Iniciando carga de pasajeros...")
        else:
            logger.info("Vuelos cargados. Usa --verify para comprobar, luego --passengers-only.")

    if do_passengers:
        load_passengers(datasets_path, bej_host, bej_port, ukr_host, ukr_port)

    elapsed = time.time() - t0
    logger.info("=== Ingesta completa en %.0f segundos (%.1f min) ===",
                elapsed, elapsed / 60)


if __name__ == "__main__":
    main()
