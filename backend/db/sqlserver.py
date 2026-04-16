"""
db/sqlserver.py
───────────────
Gestiona las conexiones a los dos nodos SQL Server (Beijing y Ucrania).
Expone funciones de lectura/escritura para flights, passengers
y reservations.

Usa pyodbc directamente (sin ORM) para mayor control sobre los
tipos de SQL Server y para facilitar el manejo de errores de conexión.
"""
import json
import logging
from contextlib import contextmanager
from typing import Any

import pyodbc

from config import settings

logger = logging.getLogger(__name__)

# ── Cadenas de conexión ───────────────────────────────────────

def _conn_str(host: str, port: int) -> str:
    return (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={host},{port};"
        f"DATABASE={settings.sql_database};"
        f"UID={settings.sql_user};"
        f"PWD={settings.sql_password};"
        "TrustServerCertificate=yes;"
        "Connection Timeout=5;"
    )

CONN_STRINGS: dict[str, str] = {
    "beijing": _conn_str(settings.sql_beijing_host, settings.sql_beijing_port),
    "ukraine": _conn_str(settings.sql_ukraine_host, settings.sql_ukraine_port),
}


# ── Obtención de conexión ─────────────────────────────────────

@contextmanager
def get_conn(node: str):
    """
    Context manager que entrega una conexión pyodbc para el nodo dado.
    Cierra y libera la conexión al salir del bloque.
    Lanza ConnectionError si el nodo no está disponible.
    """
    try:
        conn = pyodbc.connect(CONN_STRINGS[node], timeout=5)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    except pyodbc.Error as exc:
        raise ConnectionError(f"[{node}] SQL Server no disponible: {exc}") from exc


def is_online(node: str) -> bool:
    """Comprueba si el nodo SQL Server responde."""
    try:
        with get_conn(node) as conn:
            conn.execute("SELECT 1")
        return True
    except (ConnectionError, pyodbc.Error):
        return False


# ── Lectura: vuelos ───────────────────────────────────────────

def get_flights(node: str, filters: dict | None = None) -> list[dict]:
    """
    Devuelve vuelos del nodo dado aplicando filtros opcionales:
    origin, destination, flight_date, status.
    """
    query = "SELECT * FROM flights WHERE 1=1"
    params: list[Any] = []

    if filters:
        if "origin" in filters:
            query += " AND origin = ?"
            params.append(filters["origin"])
        if "destination" in filters:
            query += " AND destination = ?"
            params.append(filters["destination"])
        if "flight_date" in filters:
            query += " AND flight_date = ?"
            params.append(filters["flight_date"])
        if "status" in filters:
            query += " AND status = ?"
            params.append(filters["status"])

    query += " ORDER BY flight_date, departure_time"

    with get_conn(node) as conn:
        cursor = conn.execute(query, params)
        cols = [col[0] for col in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]


def get_flight_by_id(node: str, flight_id: int) -> dict | None:
    with get_conn(node) as conn:
        cursor = conn.execute("SELECT * FROM flights WHERE id = ?", flight_id)
        cols = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        return dict(zip(cols, row)) if row else None


# ── Escritura: reservas ───────────────────────────────────────

def insert_reservation(node: str, data: dict) -> None:
    """
    Inserta una reserva en el nodo dado.
    data debe incluir todos los campos de la tabla reservations.
    """
    sql = """
        INSERT INTO reservations
            (id, transaction_id, flight_id, passenger_passport,
             seat_number, cabin_class, status, price_paid,
             node_origin, vector_clock, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,GETUTCDATE(),GETUTCDATE())
    """
    with get_conn(node) as conn:
        conn.execute(sql, (
            data["id"],
            data["transaction_id"],
            data["flight_id"],
            data["passenger_passport"],
            data["seat_number"],
            data["cabin_class"],
            data["status"],
            data["price_paid"],
            data["node_origin"],
            data["vector_clock"],   # JSON string
        ))
        # Decrementar disponibilidad del vuelo
        col = "available_first" if data["cabin_class"] == "FIRST" else "available_economy"
        conn.execute(f"UPDATE flights SET {col} = {col} - 1 WHERE id = ?",
                     data["flight_id"])


def cancel_reservation(node: str, transaction_id: str, vector_clock: str) -> None:
    """Cambia el status de una reserva a CANCELLED."""
    sql = """
        UPDATE reservations
        SET status = 'CANCELLED', vector_clock = ?, updated_at = GETUTCDATE()
        WHERE transaction_id = ?
    """
    with get_conn(node) as conn:
        conn.execute(sql, (vector_clock, transaction_id))


def get_reservations_for_flight(node: str, flight_id: int) -> list[dict]:
    with get_conn(node) as conn:
        cursor = conn.execute(
            "SELECT * FROM reservations WHERE flight_id = ? AND status = 'CONFIRMED'",
            flight_id
        )
        cols = [col[0] for col in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]


def get_reservation_by_transaction_id(node: str, transaction_id: str) -> dict | None:
    with get_conn(node) as conn:
        cursor = conn.execute(
            "SELECT * FROM reservations WHERE transaction_id = ?", transaction_id
        )
        cols = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        return dict(zip(cols, row)) if row else None


# ── Lectura: pasajeros ────────────────────────────────────────

def get_passenger(node: str, passport: str) -> dict | None:
    with get_conn(node) as conn:
        cursor = conn.execute(
            "SELECT * FROM passengers WHERE passport = ?", passport
        )
        cols = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        return dict(zip(cols, row)) if row else None


# ── Sync queue ────────────────────────────────────────────────

def enqueue_sync(node: str, transaction_id: str, operation_type: str,
                 target_node: str, payload: dict, vector_clock: str) -> None:
    """Agrega una operación pendiente a la cola de sincronización."""
    sql = """
        INSERT INTO sync_queue
            (transaction_id, operation_type, target_node, payload, vector_clock)
        VALUES (?,?,?,?,?)
    """
    with get_conn(node) as conn:
        conn.execute(sql, (
            transaction_id,
            operation_type,
            target_node,
            json.dumps(payload),
            vector_clock,
        ))


def get_pending_sync(node: str, target_node: str) -> list[dict]:
    """Devuelve operaciones pendientes de replicar a target_node."""
    with get_conn(node) as conn:
        cursor = conn.execute(
            "SELECT * FROM sync_queue WHERE target_node = ? AND replayed = 0 ORDER BY queued_at",
            target_node
        )
        cols = [col[0] for col in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]


def mark_sync_replayed(node: str, sync_id: int) -> None:
    with get_conn(node) as conn:
        conn.execute("UPDATE sync_queue SET replayed = 1 WHERE id = ?", sync_id)
