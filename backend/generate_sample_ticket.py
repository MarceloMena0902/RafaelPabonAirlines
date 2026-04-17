"""
generate_sample_ticket.py
──────────────────────────
Genera un boarding pass PDF de muestra y lo guarda en
backend/context/sample_boarding_pass.pdf

Uso:
    cd "E:/ISI trabajos/7moSem/Sistemas Distribuidos/Practica3/backend"
    python generate_sample_ticket.py

Requiere:
    pip install fpdf2 qrcode[pil] Pillow
"""
import io
import json
import os
import sys
from pathlib import Path

# Permite ejecutar desde cualquier carpeta
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

try:
    from fpdf import FPDF
    import qrcode
except ImportError:
    print("ERROR: pip install fpdf2 qrcode[pil] Pillow")
    sys.exit(1)

OUTPUT = ROOT / "context" / "sample_boarding_pass.pdf"

# ── Paleta RafaelPabonAirlines ────────────────────────────────
_WINE   = (139, 27, 61)
_NAVY   = (10,  31, 68)
_GOLD   = (212, 160, 23)
_WHITE  = (255, 255, 255)
_GRAY   = (245, 245, 245)
_DGRAY  = (100, 100, 100)

LOGO_PATH = str(ROOT / "context" / "logo.png")

AIRPORT_NAMES = {
    "PEK": "Pekín Capital International",
    "ATL": "Atlanta Hartsfield-Jackson",
    "DXB": "Dubai Internacional",
    "LON": "Londres Heathrow",
    "PAR": "París Charles de Gaulle",
}


def _make_qr_bytes(text: str) -> bytes:
    qr = qrcode.QRCode(version=2, box_size=6, border=2)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def build_sample_pdf() -> bytes:
    # ── Datos de muestra ─────────────────────────────────────
    reservation = {
        "transaction_id":    "BEJ-1745481600123-000042",
        "cabin_class":       "ECONOMY",
        "status":            "CONFIRMED",
        "price_paid":        850.00,
        "node_origin":       "beijing",
        "passenger_passport":"LA28169216",
        "seat_number":       "22C",
        "vector_clock":      json.dumps({"beijing": 42, "ukraine": 0, "lapaz": 0}),
        "flight_id":         10001,
    }
    flight = {
        "id":            10001,
        "origin":        "ATL",
        "destination":   "PEK",
        "flight_date":   "2026-06-15",
        "departure_time":"14:30:00",
        "gate":          "B22",
        "node_owner":    "beijing",
    }
    passenger = {
        "full_name":    "Juan Pablo Pérez García",
        "nationality":  "boliviana",
    }

    pdf = FPDF(orientation="L", unit="mm", format="A5")
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    W, H  = 210, 148
    PANEL = 132

    # ── Fondo blanco ─────────────────────────────────────────
    pdf.set_fill_color(*_WHITE)
    pdf.rect(0, 0, W, H, "F")

    # ── Panel wine izquierdo ──────────────────────────────────
    pdf.set_fill_color(*_WINE)
    pdf.rect(0, 0, PANEL, H, "F")

    # ── Franja dorada superior ────────────────────────────────
    pdf.set_fill_color(*_GOLD)
    pdf.rect(0, 0, PANEL, 6, "F")

    # ── Logo (si existe) ──────────────────────────────────────
    logo_x, logo_y, logo_h = 6, 9, 14
    if os.path.exists(LOGO_PATH):
        try:
            pdf.image(LOGO_PATH, x=logo_x, y=logo_y, h=logo_h)
        except Exception:
            pass

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*_WHITE)
    pdf.set_xy(logo_x + 18, logo_y + 1)
    pdf.cell(80, 5, "RAFAEL PABÓN AIRLINES", ln=0)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_xy(logo_x + 18, logo_y + 7)
    pdf.cell(80, 4, "BOARDING PASS - MUESTRA / SAMPLE", ln=0)

    # ── Ruta ─────────────────────────────────────────────────
    origin      = flight["origin"]
    destination = flight["destination"]
    orig_name   = AIRPORT_NAMES.get(origin, origin)
    dest_name   = AIRPORT_NAMES.get(destination, destination)

    pdf.set_font("Helvetica", "B", 34)
    pdf.set_text_color(*_WHITE)
    pdf.set_xy(6, 28)
    pdf.cell(42, 18, origin, ln=0, align="C")

    pdf.set_font("Helvetica", "", 20)
    pdf.set_text_color(*_GOLD)
    pdf.set_xy(48, 32)
    pdf.cell(14, 10, "->", ln=0, align="C")

    pdf.set_font("Helvetica", "B", 34)
    pdf.set_text_color(*_WHITE)
    pdf.set_xy(62, 28)
    pdf.cell(42, 18, destination, ln=0, align="C")

    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(220, 180, 195)
    pdf.set_xy(6, 45)
    pdf.cell(50, 4, orig_name[:30], ln=0)
    pdf.set_xy(62, 45)
    pdf.cell(50, 4, dest_name[:30], ln=0)

    # ── Separador dorado ──────────────────────────────────────
    pdf.set_draw_color(*_GOLD)
    pdf.set_line_width(0.3)
    pdf.line(6, 52, PANEL - 6, 52)

    # ── Campos de vuelo ───────────────────────────────────────
    def field(x, y, label, value, w=28):
        pdf.set_font("Helvetica", "", 6)
        pdf.set_text_color(200, 160, 175)
        pdf.set_xy(x, y)
        pdf.cell(w, 4, label.upper(), ln=0)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*_WHITE)
        pdf.set_xy(x, y + 4)
        pdf.cell(w, 5, str(value)[:18], ln=0)

    field(6,  56, "Fecha",      "15 Jun 2026")
    field(38, 56, "Hora",       "14:30")
    field(68, 56, "Puerta",     flight["gate"])
    field(98, 56, "Vuelo #",    str(flight["id"]))
    field(6,  72, "Clase",      "Económica", w=50)
    field(68, 72, "Asiento",    reservation["seat_number"])
    field(98, 72, "Nodo",       "Pekín")

    # ── Pasajero ─────────────────────────────────────────────
    pdf.set_font("Helvetica", "", 6)
    pdf.set_text_color(200, 160, 175)
    pdf.set_xy(6, 89)
    pdf.cell(120, 4, "PASAJERO", ln=0)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*_WHITE)
    pdf.set_xy(6, 93)
    pdf.cell(120, 6, passenger["full_name"][:35], ln=0)

    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(200, 160, 175)
    pdf.set_xy(6, 100)
    pdf.cell(120, 4,
             f"Pasaporte: {reservation['passenger_passport']}   "
             f"Nacionalidad: {passenger['nationality']}", ln=0)

    # ── Precio ───────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*_GOLD)
    pdf.set_xy(6, 108)
    pdf.cell(60, 6, f"USD {reservation['price_paid']:,.2f}", ln=0)

    # ── Franja dorada inferior ────────────────────────────────
    pdf.set_fill_color(*_GOLD)
    pdf.rect(0, H - 7, PANEL, 7, "F")
    pdf.set_font("Helvetica", "", 6)
    pdf.set_text_color(*_NAVY)
    pdf.set_xy(6, H - 6)
    pdf.cell(PANEL - 12, 5, "Gracias por volar con RafaelPabonAirlines. Buen viaje.", ln=0)

    # ── Panel derecho (talón) ─────────────────────────────────
    pdf.set_draw_color(*_DGRAY)
    pdf.set_line_width(0.3)
    for y in range(5, H - 5, 4):
        pdf.line(PANEL + 1, y, PANEL + 1, y + 2)

    # QR Code
    qr_bytes = _make_qr_bytes(reservation["transaction_id"])
    pdf.image(io.BytesIO(qr_bytes), x=PANEL + 8, y=10, w=50, h=50, type="PNG")

    pdf.set_font("Helvetica", "", 6)
    pdf.set_text_color(*_DGRAY)
    pdf.set_xy(PANEL + 5, 63)
    pdf.cell(W - PANEL - 8, 4, "Escanea para verificar", ln=0, align="C")

    # Transaction ID vertical
    tx = reservation["transaction_id"]
    with pdf.rotation(90, x=PANEL + 6, y=75):
        pdf.set_xy(PANEL + 6 - 30, 75 - 3)
        pdf.set_font("Helvetica", "", 6)
        pdf.set_text_color(*_DGRAY)
        pdf.cell(60, 4, tx, ln=0, align="C")

    # Badge de estado
    pdf.set_fill_color(*_WINE)
    pdf.set_text_color(*_WHITE)
    pdf.set_font("Helvetica", "B", 8)
    badge_w, badge_h = 36, 8
    badge_x = PANEL + (W - PANEL - badge_w) / 2
    pdf.rect(badge_x, H - 20, badge_w, badge_h, "F")
    pdf.set_xy(badge_x, H - 20)
    pdf.cell(badge_w, badge_h, "CONFIRMED", ln=0, align="C")

    # Vector Clock
    vc = json.loads(reservation["vector_clock"])
    vc_str = f"VC: B{vc.get('beijing',0)} U{vc.get('ukraine',0)} LP{vc.get('lapaz',0)}"
    pdf.set_font("Helvetica", "", 5)
    pdf.set_text_color(*_DGRAY)
    pdf.set_xy(PANEL + 4, H - 9)
    pdf.cell(W - PANEL - 6, 4, vc_str, ln=0, align="C")

    return bytes(pdf.output())


if __name__ == "__main__":
    OUTPUT.parent.mkdir(exist_ok=True)
    pdf_bytes = build_sample_pdf()
    OUTPUT.write_bytes(pdf_bytes)
    print(f"✓ Boarding pass de muestra generado: {OUTPUT}")
    print(f"  Tamaño: {len(pdf_bytes):,} bytes")
    print()
    print("  El PDF muestra:")
    print("  • Panel wine (izquierda): logo + ruta ATL→PEK + datos de vuelo + pasajero + precio")
    print("  • Panel blanco (derecha): código QR + transaction_id vertical + badge CONFIRMED + Vector Clock")
    print()
    print("  Para generar el boarding pass real de una reserva:")
    print("  GET http://localhost:8000/reservations/{transaction_id}/ticket  → visualizar inline")
    print("  GET http://localhost:8000/reservations/{transaction_id}/wallet  → descargar como archivo")
