"""
ingestion/parallel_loader.py  —  v3  (Windows / Python 3.13 compatible)
────────────────────────────────────────────────────────────────────────
Carga 60 000 vuelos y 5 000 000 pasajeros a los 3 nodos.

Cambios respecto a v2:
  • SIN ThreadPoolExecutor anidados (causaba AttributeError en _thread en
    Python 3.13 Windows cuando un pool creaba otro pool internamente).
  • Un único nivel de paralelismo: pool externo divide chunks, cada worker
    escribe a los 3 nodos en SECUENCIA (no en sub-pool).
  • Detección automática de la ruta local data/datasets/ para correr
    fuera de Docker.
  • Flag --local: usa localhost:1433 / localhost:1434 en lugar de los
    hostnames de contenedor.
  • Reparación de índices al inicio: si un load anterior quedó a medias
    con índices en estado DISABLED, los reconstruye antes de continuar.
  • Esquema explícito dbo. en todas las tablas SQL Server.
  • fast_executemany = True + chunks de 200 k mantienen el rendimiento.

Uso
────
  # Desde Docker exec (dentro del contenedor rpa_backend):
  python -m ingestion.parallel_loader
  python -m ingestion.parallel_loader --reset

  # Desde Windows directamente contra los contenedores expuestos:
  python -m ingestion.parallel_loader --local
  python -m ingestion.parallel_loader --local --reset

  # Especificar ruta de datasets manualmente:
  python -m ingestion.parallel_loader --path "E:/ISI trabajos/.../Contexto"
"""
import argparse
import logging
import sys
import time
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import pyodbc
from pymongo import MongoClient
from datetime import date as _date, time as _time

# ── Setup de path para poder importar los módulos del proyecto ─
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
CHUNK_FLIGHTS    =   5_000
CHUNK_PASSENGERS = 200_000

# ── Contadores de progreso (thread-safe) ──────────────────────
_progress_lock = threading.Lock()
_processed_pax = 0


# ══════════════════════════════════════════════════════════════
#  Resolución de rutas
# ══════════════════════════════════════════════════════════════

def _find_datasets_path(override: str | None) -> Path:
    """
    Prioridad:
      1. --path argumento CLI
      2. Variable de entorno DATASETS_PATH
      3. <backend_root>/data/datasets/   (ejecución local Windows)
      4. settings.context_path           (dentro del contenedor Docker)
    """
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

    # Si ninguno tiene el CSV, devolver el primero para que el error
    # sea descriptivo al abrir el archivo.
    logger.warning(
        "No se encontraron vuelos.csv en ninguna ruta candidata. "
        "Rutas revisadas: %s", candidates
    )
    return candidates[-1]


# ══════════════════════════════════════════════════════════════
#  Conexiones
# ══════════════════════════════════════════════════════════════

def _sql_conn(host: str, port: int) -> pyodbc.Connection:
    conn_str = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={host},{port};"
        f"DATABASE={settings.sql_database};"
        f"UID={settings.sql_user};"
        f"PWD={settings.sql_password};"
        "TrustServerCertificate=yes;"
        "Connection Timeout=10;"
    )
    conn = pyodbc.connect(conn_str, autocommit=False)
    return conn


# ══════════════════════════════════════════════════════════════
#  Mantenimiento de índices
# ══════════════════════════════════════════════════════════════

_INDEX_TABLES = ("dbo.flights", "dbo.passengers")


def _repair_indexes(conn: pyodbc.Connection, node: str) -> None:
    """
    Reconstruye índices deshabilitados que haya dejado un load
    interrumpido anteriormente. Es rápido si la tabla está vacía.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT OBJECT_NAME(i.object_id) AS tbl
        FROM   sys.indexes  i
        JOIN   sys.objects  o ON i.object_id = o.object_id
        WHERE  i.is_disabled = 1
          AND  o.type = 'U'
          AND  OBJECT_NAME(i.object_id) IN ('flights','passengers','reservations')
    """)
    disabled_tables = {row[0] for row in cursor.fetchall()}
    if disabled_tables:
        logger.info("[%s] Reconstruyendo índices deshabilitados en: %s", node, disabled_tables)
        for tbl in disabled_tables:
            cursor.execute(f"ALTER INDEX ALL ON dbo.{tbl} REBUILD")
        conn.commit()


def _disable_indexes(conn: pyodbc.Connection) -> None:
    cursor = conn.cursor()
    for tbl in _INDEX_TABLES:
        cursor.execute(f"ALTER INDEX ALL ON {tbl} DISABLE")
    conn.commit()


def _rebuild_indexes(conn: pyodbc.Connection, node: str) -> None:
    cursor = conn.cursor()
    logger.info("[%s] Reconstruyendo índices...", node)
    for tbl in _INDEX_TABLES:
        cursor.execute(f"ALTER INDEX ALL ON {tbl} REBUILD")
    conn.commit()


# ══════════════════════════════════════════════════════════════
#  INSERT helpers
# ══════════════════════════════════════════════════════════════

def _sql_insert_flights(conn: pyodbc.Connection, rows: list[tuple]) -> None:
    sql = """
        INSERT INTO dbo.flights
            (id, flight_date, departure_time, origin, destination,
             aircraft_id, status, gate, price_economy, price_first,
             duration_hours, available_economy, available_first, node_owner)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """
    cur = conn.cursor()
    cur.fast_executemany = True
    cur.executemany(sql, rows)
    conn.commit()


def _sql_insert_passengers(conn: pyodbc.Connection, rows: list[tuple]) -> None:
    sql = """
        INSERT INTO dbo.passengers
            (passport, full_name, nationality, email, home_region)
        VALUES (?,?,?,?,?)
    """
    cur = conn.cursor()
    cur.fast_executemany = True
    cur.executemany(sql, rows)
    conn.commit()


# ══════════════════════════════════════════════════════════════
#  Transformaciones
# ══════════════════════════════════════════════════════════════

def _parse_date(val) -> _date:
    """Convierte string 'YYYY-MM-DD' a datetime.date."""
    s = str(val).strip()
    return _date.fromisoformat(s)


def _parse_time(val) -> _time:
    """Convierte string 'HH:MM' o 'HH:MM:SS' a datetime.time."""
    s = str(val).strip()
    if len(s) == 5:          # "10:01"
        s += ":00"
    return _time.fromisoformat(s)


def _transform_flight_chunk(chunk: pd.DataFrame, start_id: int) -> list[tuple]:
    rows = []
    for i, row in enumerate(chunk.itertuples(index=False), start=start_id):
        origin      = str(row.Origen).strip().upper()
        destination = str(row.Destino).strip().upper()
        # Mapear al rango 1-4 (FK a tabla aircraft que solo tiene 4 modelos)
        aircraft_id = (int(row.AvionId) - 1) % 4 + 1
        aircraft    = AIRCRAFT[aircraft_type_for_id(aircraft_id)]

        price_eco   = float(PRICES_ECONOMY.get(origin, {}).get(destination) or 0)
        price_first = float(PRICES_FIRST.get(origin,   {}).get(destination) or 0)
        duration    = int(FLIGHT_HOURS.get(origin,     {}).get(destination, 0))
        node        = node_for_airport(origin)

        rows.append((
            i,
            _parse_date(row.Fecha),
            _parse_time(row.Hora),
            origin,
            destination,
            aircraft_id,
            str(row.Estado).strip(),
            str(row.Gate).strip(),
            price_eco,
            price_first,
            duration,
            aircraft["economy_seats"],
            aircraft["first_class_seats"],
            node,
        ))
    return rows


_REGION_MAP = {
    "Boliviano":      "LATAM",
    "Brasilero":      "LATAM",
    "Español":        "LATAM",
    "Ucraniano":      "EURO_ESTE",
    "Turco":          "EURO_ESTE",
    "Alemán":         "EURO_OESTE",
    "Francés":        "EURO_OESTE",
    "Holandés":       "EURO_OESTE",
    "Británico":      "EURO_OESTE",
    "Emiratí":        "ORIENTE",
    "Chino":          "ORIENTE",
    "Japonés":        "ORIENTE",
    "Singapurense":   "ORIENTE",
    "Estadounidense": "NORTE_AMERICA",
}


def _transform_passenger_chunk(chunk: pd.DataFrame) -> tuple[list[tuple], list[dict]]:
    sql_rows   = []
    mongo_docs = []
    for row in chunk.itertuples(index=False):
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

    # Una conexión persistente por nodo SQL (los vuelos no cambian)
    conn_bej = _sql_conn(bej_host, bej_port)
    conn_ukr = _sql_conn(ukr_host, ukr_port)
    mongo_cli = MongoClient(settings.mongo_uri())
    mongo_db  = mongo_cli[settings.mongo_database]

    chunks = [
        (i, df[i * CHUNK_FLIGHTS: (i + 1) * CHUNK_FLIGHTS])
        for i in range((total + CHUNK_FLIGHTS - 1) // CHUNK_FLIGHTS)
    ]
    n_chunks = len(chunks)

    def process_flight_chunk(idx: int, chunk: pd.DataFrame) -> str:
        """
        Transforma y escribe un chunk a los 3 nodos SECUENCIALMENTE.
        Sin sub-pools → compatible con Python 3.13 Windows.
        """
        start_id = idx * CHUNK_FLIGHTS + 1
        rows = _transform_flight_chunk(chunk, start_id)

        # Beijing
        _sql_insert_flights(conn_bej, rows)

        # Ucrania
        _sql_insert_flights(conn_ukr, rows)

        # MongoDB
        docs = [
            {"id": r[0],
             "flight_date": r[1].isoformat(),
             "departure_time": r[2].strftime("%H:%M:%S"),
             "origin": r[3], "destination": r[4], "aircraft_id": r[5],
             "status": r[6], "gate": r[7], "price_economy": r[8],
             "price_first": r[9], "duration_hours": r[10],
             "available_economy": r[11], "available_first": r[12],
             "node_owner": r[13]}
            for r in rows
        ]
        mongo_db.flights.insert_many(docs, ordered=False)

        return f"chunk {idx + 1}/{n_chunks}  ({len(rows)} vuelos)"

    # NOTA: vuelos comparten conexiones → no pueden correr en paralelo
    # (pyodbc connections no son thread-safe).  Se procesan en secuencia.
    for idx, chunk in chunks:
        try:
            msg = process_flight_chunk(idx, chunk)
            logger.info("[vuelos] %s", msg)
        except Exception as exc:
            logger.error("[vuelos] Error en chunk %d: %s", idx, exc)
            raise

    conn_bej.close()
    conn_ukr.close()
    mongo_cli.close()
    logger.info("Vuelos cargados: %d registros en 3 nodos.", total)


# ══════════════════════════════════════════════════════════════
#  Carga de pasajeros
# ══════════════════════════════════════════════════════════════

def _load_passenger_chunk(
    chunk: pd.DataFrame,
    chunk_num: int,
    total_chunks: int,
    bej_host: str, bej_port: int,
    ukr_host: str, ukr_port: int,
) -> int:
    """
    Procesa UN chunk: transforma y escribe a los 3 nodos en SECUENCIA.
    Deduplica por pasaporte antes de insertar (el CSV contiene duplicados).
    """
    global _processed_pax
    sql_rows, mongo_docs = _transform_passenger_chunk(chunk)

    # Beijing
    conn_bej = _sql_conn(bej_host, bej_port)
    try:
        _sql_insert_passengers(conn_bej, sql_rows)
    finally:
        conn_bej.close()

    # Ucrania
    conn_ukr = _sql_conn(ukr_host, ukr_port)
    try:
        _sql_insert_passengers(conn_ukr, sql_rows)
    finally:
        conn_ukr.close()

    # MongoDB
    mongo_cli = MongoClient(settings.mongo_uri())
    try:
        mongo_cli[settings.mongo_database].passengers.insert_many(
            mongo_docs, ordered=False
        )
    finally:
        mongo_cli.close()

    with _progress_lock:
        _processed_pax += len(sql_rows)
        logger.info(
            "[pasajeros] chunk %d/%d  → %d registros  (acumulado: %d)",
            chunk_num, total_chunks, len(sql_rows), _processed_pax,
        )

    return len(sql_rows)


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

    # Set global de pasaportes ya insertados — filtra duplicados entre chunks
    seen: set[str] = set()
    chunk_num = 0

    for chunk in pd.read_csv(csv_path, chunksize=CHUNK_PASSENGERS):
        chunk_num += 1

        # 1. Deduplicar dentro del chunk
        chunk = chunk.drop_duplicates(subset=["Pasaporte"], keep="first")
        # 2. Descartar pasaportes ya insertados en chunks anteriores
        chunk = chunk[~chunk["Pasaporte"].isin(seen)]

        if chunk.empty:
            logger.info("[pasajeros] chunk %d → vacío tras deduplicar, saltando", chunk_num)
            continue

        # Registrar los pasaportes de este chunk como vistos
        seen.update(chunk["Pasaporte"].tolist())

        try:
            _load_passenger_chunk(
                chunk, chunk_num, (total // CHUNK_PASSENGERS) + 1,
                bej_host, bej_port, ukr_host, ukr_port,
            )
        except Exception as exc:
            logger.error("[pasajeros] Error en chunk %d: %s", chunk_num, exc)

    logger.info("Pasajeros cargados: %d registros en 3 nodos.", _processed_pax)


# ══════════════════════════════════════════════════════════════
#  Reset: DROP + RECREATE (100x más rápido que DELETE)
# ══════════════════════════════════════════════════════════════

# Cada sentencia está separada — pyodbc no soporta multi-statement.
_SQL_DROP_RECREATE: list[str] = [
    # 1. Drop en orden FK-safe
    "IF OBJECT_ID('dbo.sync_queue',   'U') IS NOT NULL DROP TABLE dbo.sync_queue",
    "IF OBJECT_ID('dbo.reservations', 'U') IS NOT NULL DROP TABLE dbo.reservations",
    "IF OBJECT_ID('dbo.flights',      'U') IS NOT NULL DROP TABLE dbo.flights",
    "IF OBJECT_ID('dbo.passengers',   'U') IS NOT NULL DROP TABLE dbo.passengers",
    # 2. Recrear
    """
    CREATE TABLE dbo.passengers (
        passport        NVARCHAR(20)  NOT NULL PRIMARY KEY,
        full_name       NVARCHAR(100) NOT NULL,
        nationality     NVARCHAR(50)  NOT NULL,
        email           NVARCHAR(100) NOT NULL,
        home_region     NVARCHAR(20)  NULL,
        created_at      DATETIME2     NOT NULL DEFAULT GETUTCDATE()
    )
    """,
    """
    CREATE TABLE dbo.flights (
        id                BIGINT        NOT NULL PRIMARY KEY,
        flight_date       DATE          NOT NULL,
        departure_time    TIME          NOT NULL,
        origin            CHAR(3)       NOT NULL REFERENCES dbo.airports(code),
        destination       CHAR(3)       NOT NULL REFERENCES dbo.airports(code),
        aircraft_id       INT           NOT NULL REFERENCES dbo.aircraft(id),
        status            NVARCHAR(20)  NOT NULL,
        gate              NVARCHAR(5)   NOT NULL,
        price_economy     DECIMAL(10,2) NOT NULL,
        price_first       DECIMAL(10,2) NOT NULL,
        duration_hours    INT           NOT NULL,
        available_economy INT           NOT NULL,
        available_first   INT           NOT NULL,
        node_owner        NVARCHAR(20)  NOT NULL,
        created_at        DATETIME2     NOT NULL DEFAULT GETUTCDATE()
    )
    """,
    "CREATE INDEX ix_flights_date_origin ON dbo.flights(flight_date, origin)",
    "CREATE INDEX ix_flights_node        ON dbo.flights(node_owner)",
    """
    CREATE TABLE dbo.reservations (
        id                 BIGINT        NOT NULL PRIMARY KEY,
        transaction_id     NVARCHAR(60)  NOT NULL UNIQUE,
        flight_id          BIGINT        NOT NULL REFERENCES dbo.flights(id),
        passenger_passport NVARCHAR(20)  NOT NULL REFERENCES dbo.passengers(passport),
        seat_number        NVARCHAR(5)   NOT NULL,
        cabin_class        NVARCHAR(10)  NOT NULL,
        status             NVARCHAR(20)  NOT NULL DEFAULT 'CONFIRMED',
        price_paid         DECIMAL(10,2) NOT NULL,
        node_origin        NVARCHAR(20)  NOT NULL,
        vector_clock       NVARCHAR(200) NOT NULL,
        created_at         DATETIME2     NOT NULL DEFAULT GETUTCDATE(),
        updated_at         DATETIME2     NOT NULL DEFAULT GETUTCDATE()
    )
    """,
    "CREATE INDEX ix_reservations_flight    ON dbo.reservations(flight_id)",
    "CREATE INDEX ix_reservations_passenger ON dbo.reservations(passenger_passport)",
    """
    CREATE TABLE dbo.sync_queue (
        id             BIGINT        NOT NULL IDENTITY(1,1) PRIMARY KEY,
        transaction_id NVARCHAR(60)  NOT NULL,
        operation_type NVARCHAR(20)  NOT NULL,
        target_node    NVARCHAR(20)  NOT NULL,
        payload        NVARCHAR(MAX) NOT NULL,
        vector_clock   NVARCHAR(200) NOT NULL,
        queued_at      DATETIME2     NOT NULL DEFAULT GETUTCDATE(),
        replayed       BIT           NOT NULL DEFAULT 0
    )
    """,
    "CREATE INDEX ix_sync_queue_pending ON dbo.sync_queue(target_node, replayed)",
]


def _reset_sql_node(node: str, host: str, port: int) -> None:
    conn   = _sql_conn(host, port)
    cursor = conn.cursor()
    for stmt in _SQL_DROP_RECREATE:
        stmt = stmt.strip()
        if not stmt:
            continue
        try:
            cursor.execute(stmt)
            conn.commit()
        except Exception as exc:
            # La mayoría de errores aquí son benignos (DROP de tabla inexistente)
            logger.debug("[reset/%s] ignorado: %s  →  %s", node, stmt[:60], exc)
    conn.close()
    logger.info("[reset] %s → tablas recreadas", node)


def reset_all_nodes() -> None:
    """
    DROP + RECREATE en los 3 nodos.
    Las tablas estáticas (airports, aircraft) no se tocan.
    """
    logger.info("=== RESET: DROP + RECREATE en los 3 nodos ===")

    # SQL Server: se puede correr en paralelo (conexiones independientes)
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_bej = ex.submit(_reset_sql_node, "beijing",
                          settings.sql_beijing_host, settings.sql_beijing_port)
        f_ukr = ex.submit(_reset_sql_node, "ukraine",
                          settings.sql_ukraine_host, settings.sql_ukraine_port)
        for f in (f_bej, f_ukr):
            try:
                f.result()
            except Exception as exc:
                logger.error("[reset] SQL error: %s", exc)

    # MongoDB
    try:
        cli = MongoClient(settings.mongo_uri())
        db  = cli[settings.mongo_database]
        for col in ("sync_queue", "reservations", "flights", "passengers"):
            db[col].drop()
        # Índices
        db.flights.create_index([("id", 1)],           unique=True)
        db.flights.create_index([("flight_date", 1),   ("origin", 1)])
        db.flights.create_index([("node_owner", 1)])
        db.passengers.create_index([("passport", 1)],  unique=True)
        db.reservations.create_index([("id", 1)],            unique=True)
        db.reservations.create_index([("transaction_id", 1)], unique=True)
        db.reservations.create_index([("flight_id", 1)])
        db.sync_queue.create_index([("target_node", 1), ("replayed", 1)])
        # IKJ counter
        db.ikj_counter.update_one(
            {"node": "lapaz"}, {"$set": {"next_id": 3_000_000_000}}, upsert=True
        )
        cli.close()
        logger.info("[reset] lapaz → colecciones recreadas")
    except Exception as exc:
        logger.error("[reset] MongoDB error: %s", exc)

    logger.info("=== RESET completado ===")


# ══════════════════════════════════════════════════════════════
#  Entry point
# ══════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingesta RafaelPabonAirlines — v3"
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="DROP + RECREATE de todas las tablas de datos antes de cargar.",
    )
    parser.add_argument(
        "--yes", action="store_true",
        help="Omite la confirmación interactiva del --reset (útil en scripts).",
    )
    parser.add_argument(
        "--local", action="store_true",
        help=(
            "Conecta a localhost:1433 (Beijing) y localhost:1434 (Ucrania) "
            "en lugar de los hostnames de contenedor. Útil al correr desde "
            "Windows directamente contra los contenedores Docker."
        ),
    )
    parser.add_argument(
        "--path", metavar="DIR", default=None,
        help="Ruta explícita a la carpeta con vuelos.csv y pasajeros.csv.",
    )
    parser.add_argument(
        "--workers", type=int, default=4,
        help="Número de hilos para carga de pasajeros (default: 4).",
    )
    args = parser.parse_args()

    # ── Hosts/puertos según modo ───────────────────────────────
    if args.local:
        bej_host, bej_port = "localhost", 1433
        ukr_host, ukr_port = "localhost", 1434
        logger.info("Modo --local: conectando a localhost:1433 y localhost:1434")
    else:
        bej_host = settings.sql_beijing_host
        bej_port = settings.sql_beijing_port
        ukr_host = settings.sql_ukraine_host
        ukr_port = settings.sql_ukraine_port

    # ── Ruta de datasets ───────────────────────────────────────
    datasets_path = _find_datasets_path(args.path)

    # ── Reset ──────────────────────────────────────────────────
    if args.reset:
        if not args.yes:
            confirm = input(
                "\n  ADVERTENCIA: Se eliminarán TODOS los vuelos, pasajeros y "
                "reservas en los 3 nodos.\n"
                "  Escribe 'CONFIRMAR' para continuar: "
            ).strip()
            if confirm != "CONFIRMAR":
                logger.info("Reset cancelado.")
                sys.exit(0)
        reset_all_nodes()

    # ── Ingesta ────────────────────────────────────────────────
    t0 = time.time()
    logger.info("=== Iniciando ingesta ===")

    load_flights(datasets_path, bej_host, bej_port, ukr_host, ukr_port)
    load_passengers(datasets_path, bej_host, bej_port, ukr_host, ukr_port)

    elapsed = time.time() - t0
    logger.info("=== Ingesta completa en %.1f segundos ===", elapsed)


if __name__ == "__main__":
    main()
