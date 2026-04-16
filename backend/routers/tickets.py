"""
routers/tickets.py
───────────────────
Genera el boarding pass en PDF para una reserva confirmada.

GET /reservations/{transaction_id}/ticket
  → descarga el PDF directamente en el navegador

GET /reservations/{transaction_id}/wallet
  → devuelve el mismo PDF con header para descarga de archivo

El PDF incluye:
  • Logo de RafaelPabonAirlines (de /app/context/logo.png si existe)
  • Código QR con el transaction_id
  • Detalle de vuelo, pasajero, asiento, clase y precio
"""
import asyncio
import io
import json
import logging
import os
from datetime import datetime

import qrcode
from fpdf import FPDF
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from db import sqlserver, mongodb
from sync.synchronizer import node_states

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reservations", tags=["Tickets"])

# Paleta de colores RafaelPabonAirlines
_WINE   = (139, 27, 61)    # #8B1B3D
_NAVY   = (10,  31, 68)    # #0A1F44
_GOLD   = (212, 160, 23)   # #D4A017
_WHITE  = (255, 255, 255)
_GRAY   = (245, 245, 245)
_DGRAY  = (100, 100, 100)

# Nombres legibles de aeropuertos
AIRPORT_NAMES: dict[str, str] = {
    "ATL": "Atlanta Hartsfield-Jackson",
    "PEK": "Pekín Capital",
    "DXB": "Dubai Internacional",
    "TYO": "Tokio Narita",
    "LON": "Londres Heathrow",
    "LAX": "Los Ángeles Internacional",
    "PAR": "París Charles de Gaulle",
    "FRA": "Fráncfort Internacional",
    "IST": "Estambul Ataturk",
    "SIN": "Singapur Changi",
    "MAD": "Madrid Barajas",
    "AMS": "Ámsterdam Schiphol",
    "DFW": "Dallas/Fort Worth",
    "CAN": "Cantón Baiyun",
    "SAO": "São Paulo Guarulhos",
}

LOGO_PATH = "/app/context/logo.png"


# ── Helpers ────────────────────────────────────────────────────

async def _fetch_reservation(transaction_id: str) -> dict:
    """Obtiene la reserva del primer nodo disponible."""
    for node in ("beijing", "ukraine"):
        if node_states[node].is_online:
            try:
                result = await asyncio.to_thread(
                    sqlserver.get_reservation_by_transaction_id, node, transaction_id
                )
                if result:
                    return result
            except Exception:
                pass
    if node_states["lapaz"].is_online:
        result = await mongodb.get_reservation_by_transaction_id(transaction_id)
        if result:
            return result
    raise HTTPException(status_code=404, detail="Reserva no encontrada.")


async def _fetch_flight(flight_id: int) -> dict:
    for node in ("beijing", "ukraine"):
        if node_states[node].is_online:
            try:
                result = await asyncio.to_thread(
                    sqlserver.get_flight_by_id, node, flight_id
                )
                if result:
                    return result
            except Exception:
                pass
    if node_states["lapaz"].is_online:
        result = await mongodb.get_flight_by_id(flight_id)
        if result:
            return result
    return {}


async def _fetch_passenger(passport: str) -> dict:
    for node in ("beijing", "ukraine"):
        if node_states[node].is_online:
            try:
                result = await asyncio.to_thread(
                    sqlserver.get_passenger, node, passport
                )
                if result:
                    return result
            except Exception:
                pass
    if node_states["lapaz"].is_online:
        result = await mongodb.get_passenger(passport)
        if result:
            return result
    return {}


def _make_qr_bytes(text: str) -> bytes:
    qr = qrcode.QRCode(version=2, box_size=6, border=2)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _node_label(node: str) -> str:
    return {"beijing": "Pekín", "ukraine": "Ucrania", "lapaz": "La Paz"}.get(node, node)


def _format_date(val) -> str:
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val).strftime("%d %b %Y")
        except Exception:
            return val
    if hasattr(val, "strftime"):
        return val.strftime("%d %b %Y")
    return str(val)


def _format_time(val) -> str:
    if val is None:
        return "--:--"
    s = str(val)
    if len(s) >= 5:
        return s[:5]
    return s


def _build_pdf(reservation: dict, flight: dict, passenger: dict) -> bytes:
    """Genera el PDF del boarding pass y devuelve bytes."""

    pdf = FPDF(orientation="L", unit="mm", format="A5")
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    W, H = 210, 148   # A5 landscape mm

    # ── Fondo completo (blanco) ───────────────────────────────
    pdf.set_fill_color(*_WHITE)
    pdf.rect(0, 0, W, H, "F")

    # ── Panel izquierdo (wine) — 130 mm ───────────────────────
    PANEL = 132
    pdf.set_fill_color(*_WINE)
    pdf.rect(0, 0, PANEL, H, "F")

    # ── Franja dorada superior ────────────────────────────────
    pdf.set_fill_color(*_GOLD)
    pdf.rect(0, 0, PANEL, 6, "F")

    # ── Logo ──────────────────────────────────────────────────
    logo_x, logo_y, logo_h = 6, 9, 14
    if os.path.exists(LOGO_PATH):
        try:
            pdf.image(LOGO_PATH, x=logo_x, y=logo_y, h=logo_h)
        except Exception:
            pass

    # Texto "RAFAEL PABÓN AIRLINES" al lado del logo
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*_WHITE)
    pdf.set_xy(logo_x + 18, logo_y + 1)
    pdf.cell(80, 5, "RAFAEL PABÓN AIRLINES", ln=0)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_xy(logo_x + 18, logo_y + 7)
    pdf.cell(80, 4, "BOARDING PASS", ln=0)

    # ── Ruta principal ────────────────────────────────────────
    origin      = flight.get("origin", reservation.get("origin", "---"))
    destination = flight.get("destination", reservation.get("destination", "---"))
    orig_name   = AIRPORT_NAMES.get(origin, origin)
    dest_name   = AIRPORT_NAMES.get(destination, destination)

    # Aeropuerto origen (grande)
    pdf.set_font("Helvetica", "B", 34)
    pdf.set_text_color(*_WHITE)
    pdf.set_xy(6, 28)
    pdf.cell(42, 18, origin, ln=0, align="C")

    # Flecha
    pdf.set_font("Helvetica", "", 20)
    pdf.set_text_color(*_GOLD)
    pdf.set_xy(48, 32)
    pdf.cell(14, 10, "->", ln=0, align="C")

    # Aeropuerto destino (grande)
    pdf.set_font("Helvetica", "B", 34)
    pdf.set_text_color(*_WHITE)
    pdf.set_xy(62, 28)
    pdf.cell(42, 18, destination, ln=0, align="C")

    # Nombres completos
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(220, 180, 195)
    pdf.set_xy(6, 45)
    pdf.cell(50, 4, orig_name[:28], ln=0)
    pdf.set_xy(62, 45)
    pdf.cell(50, 4, dest_name[:28], ln=0)

    # ── Separador ────────────────────────────────────────────
    pdf.set_draw_color(*_GOLD)
    pdf.set_line_width(0.3)
    pdf.line(6, 52, PANEL - 6, 52)

    # ── Datos de vuelo ────────────────────────────────────────
    def field_block(x, y, label, value, w=28):
        pdf.set_font("Helvetica", "", 6)
        pdf.set_text_color(200, 160, 175)
        pdf.set_xy(x, y)
        pdf.cell(w, 4, label.upper(), ln=0)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*_WHITE)
        pdf.set_xy(x, y + 4)
        pdf.cell(w, 5, str(value)[:18], ln=0)

    flight_date = _format_date(flight.get("flight_date", ""))
    dep_time    = _format_time(flight.get("departure_time"))
    gate        = str(flight.get("gate", "TBD"))
    cabin_label = "Primera Clase" if reservation.get("cabin_class") == "FIRST" else "Económica"
    seat        = reservation.get("seat_number", "---")
    flight_id   = str(flight.get("id", "---"))

    field_block(6,   56, "Fecha",     flight_date)
    field_block(38,  56, "Hora salida", dep_time)
    field_block(68,  56, "Puerta",    gate)
    field_block(98,  56, "Vuelo #",   flight_id)

    field_block(6,   72, "Clase",     cabin_label, w=50)
    field_block(68,  72, "Asiento",   seat)
    field_block(98,  72, "Nodo origen", _node_label(reservation.get("node_origin", "")))

    # ── Pasajero ─────────────────────────────────────────────
    pdf.set_font("Helvetica", "", 6)
    pdf.set_text_color(200, 160, 175)
    pdf.set_xy(6, 89)
    pdf.cell(120, 4, "PASAJERO", ln=0)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*_WHITE)
    pax_name = passenger.get("full_name", reservation.get("passenger_passport", "---"))
    pdf.set_xy(6, 93)
    pdf.cell(120, 6, pax_name[:35], ln=0)

    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(200, 160, 175)
    pdf.set_xy(6, 100)
    pax_nat = passenger.get("nationality", "")
    pax_pass = reservation.get("passenger_passport", "")
    pdf.cell(120, 4, f"Pasaporte: {pax_pass}   Nacionalidad: {pax_nat}", ln=0)

    # ── Precio ────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*_GOLD)
    price = float(reservation.get("price_paid", 0))
    pdf.set_xy(6, 108)
    pdf.cell(60, 6, f"USD {price:,.2f}", ln=0)

    # ── Franja dorada inferior ────────────────────────────────
    pdf.set_fill_color(*_GOLD)
    pdf.rect(0, H - 7, PANEL, 7, "F")
    pdf.set_font("Helvetica", "", 6)
    pdf.set_text_color(*_NAVY)
    pdf.set_xy(6, H - 6)
    pdf.cell(PANEL - 12, 5, "Gracias por volar con RafaelPabonAirlines. Buen viaje.", ln=0)

    # ── Panel derecho (blanco) ────────────────────────────────
    # Línea punteada de separación
    pdf.set_draw_color(*_DGRAY)
    pdf.set_line_width(0.3)
    for y in range(5, H - 5, 4):
        pdf.line(PANEL + 1, y, PANEL + 1, y + 2)

    # QR Code
    qr_bytes = _make_qr_bytes(reservation.get("transaction_id", "RPA"))
    qr_buf   = io.BytesIO(qr_bytes)
    qr_x, qr_y, qr_size = PANEL + 8, 10, 50
    pdf.image(qr_buf, x=qr_x, y=qr_y, w=qr_size, h=qr_size, type="PNG")

    # Etiqueta bajo el QR
    pdf.set_font("Helvetica", "", 6)
    pdf.set_text_color(*_DGRAY)
    pdf.set_xy(PANEL + 5, qr_y + qr_size + 2)
    pdf.cell(W - PANEL - 8, 4, "Escanea para verificar", ln=0, align="C")

    # Transaction ID vertical (pequeño)
    tx_id = reservation.get("transaction_id", "")
    pdf.set_font("Helvetica", "", 6)
    pdf.set_text_color(*_DGRAY)
    with pdf.rotation(90, x=PANEL + 6, y=75):
        pdf.set_xy(PANEL + 6 - 30, 75 - 3)
        pdf.cell(60, 4, tx_id, ln=0, align="C")

    # Status badge
    status = reservation.get("status", "CONFIRMED")
    badge_color = _WINE if status == "CONFIRMED" else _DGRAY
    pdf.set_fill_color(*badge_color)
    pdf.set_text_color(*_WHITE)
    pdf.set_font("Helvetica", "B", 8)
    badge_w, badge_h = 36, 8
    badge_x = PANEL + (W - PANEL - badge_w) / 2
    pdf.rect(badge_x, H - 20, badge_w, badge_h, "F")
    pdf.set_xy(badge_x, H - 20)
    pdf.cell(badge_w, badge_h, status, ln=0, align="C")

    # VC info (tiny)
    vc_raw = reservation.get("vector_clock", "")
    if vc_raw:
        try:
            vc = json.loads(vc_raw)
            vc_str = f"VC: B{vc.get('beijing',0)} U{vc.get('ukraine',0)} LP{vc.get('lapaz',0)}"
        except Exception:
            vc_str = ""
        if vc_str:
            pdf.set_font("Helvetica", "", 5)
            pdf.set_text_color(*_DGRAY)
            pdf.set_xy(PANEL + 4, H - 9)
            pdf.cell(W - PANEL - 6, 4, vc_str, ln=0, align="C")

    return bytes(pdf.output())


# ── Endpoints ──────────────────────────────────────────────────

@router.get("/{transaction_id}/ticket", summary="Descargar boarding pass PDF (inline)")
async def download_ticket(transaction_id: str):
    """
    Genera y devuelve el boarding pass en PDF.
    El navegador lo muestra en línea (no fuerza descarga).
    """
    reservation = await _fetch_reservation(transaction_id)
    flight      = await _fetch_flight(reservation.get("flight_id", 0))
    passenger   = await _fetch_passenger(reservation.get("passenger_passport", ""))

    pdf_bytes = await asyncio.to_thread(_build_pdf, reservation, flight, passenger)

    filename = f"boardingpass_{transaction_id}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )


@router.get("/{transaction_id}/wallet", summary="Descargar boarding pass PDF (attachment)")
async def download_wallet(transaction_id: str):
    """
    Igual que /ticket pero fuerza la descarga del archivo.
    """
    reservation = await _fetch_reservation(transaction_id)
    flight      = await _fetch_flight(reservation.get("flight_id", 0))
    passenger   = await _fetch_passenger(reservation.get("passenger_passport", ""))

    pdf_bytes = await asyncio.to_thread(_build_pdf, reservation, flight, passenger)

    filename = f"boardingpass_{transaction_id}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
