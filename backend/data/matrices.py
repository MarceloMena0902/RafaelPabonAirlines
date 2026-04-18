"""
data/matrices.py
────────────────
Matrices de negocio codificadas directamente desde las imágenes
de contexto (precios turista, primera clase, tiempos de vuelo
y especificaciones de la flota).

Son la fuente de verdad para calcular precios al ingestar vuelos
y para validar transacciones.
"""

# =============================================================
#  Precios Clase Turística (USD)
#  Lectura: PRICES_ECONOMY[origen][destino] → precio en USD
#  None = no existe vuelo directo entre ese par
# =============================================================
# Matriz actualizada (más rutas directas eliminadas → fuerza Dijkstra con escalas)
PRICES_ECONOMY: dict[str, dict[str, int | None]] = {
    "ATL": {"PEK":None,"DXB":None,"TYO":None,"LON":1400,"LAX":400, "PAR":None,"FRA":800, "IST":None,"SIN":None,"MAD":800, "AMS":None,"DFW":200, "CAN":None,"SAO":900 },
    "PEK": {"ATL":None,"DXB":700, "TYO":500, "LON":900, "LAX":None,"PAR":950, "FRA":None,"IST":None,"SIN":600, "MAD":950, "AMS":900, "DFW":None,"CAN":None,"SAO":None},
    "DXB": {"ATL":None,"PEK":700, "TYO":None,"LON":None,"LAX":None,"PAR":None,"FRA":None,"IST":None,"SIN":None,"MAD":None,"AMS":1200,"DFW":None,"CAN":None,"SAO":1400},
    "TYO": {"ATL":1400,"PEK":500, "DXB":None,"LON":None,"LAX":None,"PAR":None,"FRA":None,"IST":None,"SIN":None,"MAD":None,"AMS":None,"DFW":None,"CAN":None,"SAO":1100},
    "LON": {"ATL":None,"PEK":None,"DXB":650, "TYO":None,"LAX":800, "PAR":150, "FRA":400, "IST":None,"SIN":None,"MAD":200, "AMS":150, "DFW":None,"CAN":None,"SAO":1100},
    "LAX": {"ATL":None,"PEK":None,"DXB":None,"TYO":900, "LON":None,"PAR":850, "FRA":900, "IST":1100,"SIN":1400,"MAD":None,"AMS":850, "DFW":300, "CAN":None,"SAO":None},
    "PAR": {"ATL":750, "PEK":None,"DXB":None,"TYO":None,"LON":None,"LAX":850, "FRA":None,"IST":950, "SIN":None,"MAD":200, "AMS":180, "DFW":None,"CAN":None,"SAO":1050},
    "FRA": {"ATL":None,"PEK":None,"DXB":None,"TYO":950, "LON":200, "LAX":900, "PAR":150, "IST":350, "SIN":None,"MAD":None,"AMS":None,"DFW":850, "CAN":None,"SAO":None},
    "IST": {"ATL":None,"PEK":None,"DXB":None,"TYO":900, "LON":None,"LAX":2999,"PAR":None,"FRA":350, "SIN":800, "MAD":500, "AMS":450, "DFW":None,"CAN":None,"SAO":1200},
    "SIN": {"ATL":None,"PEK":None,"DXB":None,"TYO":700, "LON":900, "LAX":950, "PAR":None,"FRA":None,"IST":800, "MAD":None,"AMS":None,"DFW":None,"CAN":None,"SAO":None},
    "MAD": {"ATL":None,"PEK":None,"DXB":None,"TYO":None,"LON":200, "LAX":900, "PAR":200, "FRA":250, "IST":500, "SIN":None,"AMS":200, "DFW":None,"CAN":None,"SAO":1000},
    "AMS": {"ATL":780, "PEK":None,"DXB":None,"TYO":1000,"LON":150, "LAX":None,"PAR":None,"FRA":None,"IST":450, "SIN":None,"MAD":200, "DFW":800, "CAN":None,"SAO":None},
    "DFW": {"ATL":200, "PEK":None,"DXB":None,"TYO":None,"LON":None,"LAX":300, "PAR":800, "FRA":None,"IST":None,"SIN":None,"MAD":850, "AMS":800, "CAN":1200,"SAO":950 },
    "CAN": {"ATL":None,"PEK":None,"DXB":None,"TYO":550, "LON":None,"LAX":None,"PAR":None,"FRA":None,"IST":None,"SIN":None,"MAD":None,"AMS":900, "DFW":None,"SAO":1700},
    "SAO": {"ATL":900, "PEK":None,"DXB":None,"TYO":None,"LON":None,"LAX":None,"PAR":None,"FRA":None,"IST":None,"SIN":None,"MAD":None,"AMS":950, "DFW":None,"CAN":None},
}

# =============================================================
#  Precios Primera Clase (USD)
# =============================================================
# Primera clase: mismas rutas que económica, precio ×1.35
PRICES_FIRST: dict[str, dict[str, int | None]] = {
    "ATL": {"PEK":None,"DXB":None,"TYO":None,"LON":1890,"LAX":540, "PAR":None,"FRA":1080,"IST":None,"SIN":None,"MAD":1080,"AMS":None,"DFW":270, "CAN":None,"SAO":1215},
    "PEK": {"ATL":None,"DXB":945, "TYO":675, "LON":1215,"LAX":None,"PAR":1283,"FRA":None,"IST":None,"SIN":810, "MAD":1283,"AMS":1215,"DFW":None,"CAN":None,"SAO":None},
    "DXB": {"ATL":None,"PEK":945, "TYO":None,"LON":None,"LAX":None,"PAR":None,"FRA":None,"IST":None,"SIN":None,"MAD":None,"AMS":1620,"DFW":None,"CAN":None,"SAO":1890},
    "TYO": {"ATL":1890,"PEK":675, "DXB":None,"LON":None,"LAX":None,"PAR":None,"FRA":None,"IST":None,"SIN":None,"MAD":None,"AMS":None,"DFW":None,"CAN":None,"SAO":1485},
    "LON": {"ATL":None,"PEK":None,"DXB":878, "TYO":None,"LAX":1080,"PAR":203, "FRA":540, "IST":None,"SIN":None,"MAD":270, "AMS":203, "DFW":None,"CAN":None,"SAO":1485},
    "LAX": {"ATL":None,"PEK":None,"DXB":None,"TYO":1215,"LON":None,"PAR":1148,"FRA":1215,"IST":1485,"SIN":1890,"MAD":None,"AMS":1148,"DFW":405, "CAN":None,"SAO":None},
    "PAR": {"ATL":1013,"PEK":None,"DXB":None,"TYO":None,"LON":None,"LAX":1148,"FRA":None,"IST":1283,"SIN":None,"MAD":270, "AMS":243, "DFW":None,"CAN":None,"SAO":1418},
    "FRA": {"ATL":None,"PEK":None,"DXB":None,"TYO":1283,"LON":270, "LAX":1215,"PAR":203, "IST":473, "SIN":None,"MAD":None,"AMS":None,"DFW":1148,"CAN":None,"SAO":None},
    "IST": {"ATL":None,"PEK":None,"DXB":None,"TYO":1215,"LON":None,"LAX":4049,"PAR":None,"FRA":473, "SIN":1080,"MAD":675, "AMS":608, "DFW":None,"CAN":None,"SAO":1620},
    "SIN": {"ATL":None,"PEK":None,"DXB":None,"TYO":945, "LON":1215,"LAX":1283,"PAR":None,"FRA":None,"IST":1080,"MAD":None,"AMS":None,"DFW":None,"CAN":None,"SAO":None},
    "MAD": {"ATL":None,"PEK":None,"DXB":None,"TYO":None,"LON":270, "LAX":1215,"PAR":270, "FRA":338, "IST":675, "SIN":None,"AMS":270, "DFW":None,"CAN":None,"SAO":1350},
    "AMS": {"ATL":1053,"PEK":None,"DXB":None,"TYO":1350,"LON":203, "LAX":None,"PAR":None,"FRA":None,"IST":608, "SIN":None,"MAD":270, "DFW":1080,"CAN":None,"SAO":None},
    "DFW": {"ATL":270, "PEK":None,"DXB":None,"TYO":None,"LON":None,"LAX":405, "PAR":1080,"FRA":None,"IST":None,"SIN":None,"MAD":1148,"AMS":1080,"CAN":1620,"SAO":1283},
    "CAN": {"ATL":None,"PEK":None,"DXB":None,"TYO":743, "LON":None,"LAX":None,"PAR":None,"FRA":None,"IST":None,"SIN":None,"MAD":None,"AMS":1215,"DFW":None,"SAO":2295},
    "SAO": {"ATL":1215,"PEK":None,"DXB":None,"TYO":None,"LON":None,"LAX":None,"PAR":None,"FRA":None,"IST":None,"SIN":None,"MAD":None,"AMS":1283,"DFW":None,"CAN":None},
}

# =============================================================
#  Tiempos de vuelo en horas
# =============================================================
FLIGHT_HOURS: dict[str, dict[str, int]] = {
    "ATL": {"PEK":15,"DXB":14,"TYO":16,"LON":8, "LAX":5, "PAR":9, "FRA":9, "IST":11,"SIN":18,"MAD":8, "AMS":9, "DFW":2, "CAN":16,"SAO":9 },
    "PEK": {"ATL":15,"DXB":8, "TYO":3, "LON":10,"LAX":12,"PAR":11,"FRA":10,"IST":9, "SIN":6, "MAD":12,"AMS":10,"DFW":14,"CAN":3, "SAO":22},
    "DXB": {"ATL":14,"PEK":8, "TYO":10,"LON":7, "LAX":16,"PAR":7, "FRA":7, "IST":4, "SIN":7, "MAD":8, "AMS":7, "DFW":15,"CAN":8, "SAO":15},
    "TYO": {"ATL":16,"PEK":3, "DXB":10,"LON":12,"LAX":11,"PAR":13,"FRA":12,"IST":11,"SIN":7, "MAD":14,"AMS":12,"DFW":13,"CAN":4, "SAO":24},
    "LON": {"ATL":8, "PEK":10,"DXB":7, "TYO":12,"LAX":11,"PAR":1, "FRA":1, "IST":4, "SIN":13,"MAD":2, "AMS":1, "DFW":10,"CAN":11,"SAO":12},
    "LAX": {"ATL":5, "PEK":12,"DXB":16,"TYO":11,"LON":11,"PAR":11,"FRA":11,"IST":13,"SIN":17,"MAD":11,"AMS":11,"DFW":3, "CAN":14,"SAO":12},
    "PAR": {"ATL":9, "PEK":11,"DXB":7, "TYO":13,"LON":1, "LAX":11,"FRA":1, "IST":3, "SIN":13,"MAD":2, "AMS":1, "DFW":10,"CAN":11,"SAO":12},
    "FRA": {"ATL":9, "PEK":10,"DXB":7, "TYO":12,"LON":1, "LAX":11,"PAR":1, "IST":3, "SIN":12,"MAD":2, "AMS":1, "DFW":10,"CAN":10,"SAO":12},
    "IST": {"ATL":11,"PEK":9, "DXB":4, "TYO":11,"LON":4, "LAX":13,"PAR":3, "FRA":3, "SIN":10,"MAD":4, "AMS":3, "DFW":12,"CAN":9, "SAO":13},
    "SIN": {"ATL":18,"PEK":6, "DXB":7, "TYO":7, "LON":13,"LAX":17,"PAR":13,"FRA":12,"IST":10,"MAD":14,"AMS":13,"DFW":17,"CAN":4, "SAO":25},
    "MAD": {"ATL":8, "PEK":12,"DXB":8, "TYO":14,"LON":2, "LAX":11,"PAR":2, "FRA":2, "IST":4, "SIN":14,"AMS":2, "DFW":10,"CAN":12,"SAO":10},
    "AMS": {"ATL":9, "PEK":10,"DXB":7, "TYO":12,"LON":1, "LAX":11,"PAR":1, "FRA":1, "IST":3, "SIN":13,"MAD":2, "DFW":10,"CAN":10,"SAO":12},
    "DFW": {"ATL":2, "PEK":14,"DXB":15,"TYO":13,"LON":10,"LAX":3, "PAR":10,"FRA":10,"IST":12,"SIN":17,"MAD":10,"AMS":10,"CAN":15,"SAO":10},
    "CAN": {"ATL":16,"PEK":3, "DXB":8, "TYO":4, "LON":11,"LAX":14,"PAR":11,"FRA":10,"IST":9, "SIN":4, "MAD":12,"AMS":10,"DFW":15,"SAO":23},
    "SAO": {"ATL":9, "PEK":22,"DXB":15,"TYO":24,"LON":12,"LAX":12,"PAR":12,"FRA":12,"IST":13,"SIN":25,"MAD":10,"AMS":12,"DFW":10,"CAN":23},
}

# =============================================================
#  Flota de aeronaves
# =============================================================
AIRCRAFT: dict[str, dict] = {
    "A380": {
        "id": 1, "type_code": "A380", "manufacturer": "Airbus",
        "model": "A380-800",
        "first_class_seats": 10, "economy_seats": 439,
        "engines": "4 turbofán", "length_m": 72.7, "wingspan_m": 79.8,
        "range_km": 15200, "cruise_speed_kmh": 900, "range_mn": 8200,
    },
    "B777": {
        "id": 2, "type_code": "B777", "manufacturer": "Boeing",
        "model": "777-300ER",
        "first_class_seats": 10, "economy_seats": 300,
        "engines": "2 turbofán", "length_m": 73.9, "wingspan_m": 64.8,
        "range_km": 13650, "cruise_speed_kmh": 905, "range_mn": 7370,
    },
    "A350": {
        "id": 3, "type_code": "A350", "manufacturer": "Airbus",
        "model": "A350-900",
        "first_class_seats": 12, "economy_seats": 250,
        "engines": "2 turbofán", "length_m": 66.8, "wingspan_m": 64.8,
        "range_km": 15000, "cruise_speed_kmh": 900, "range_mn": 8100,
    },
    "B787": {
        "id": 4, "type_code": "B787", "manufacturer": "Boeing",
        "model": "787-9 Dreamliner",
        "first_class_seats": 8, "economy_seats": 220,
        "engines": "2 turbofán", "length_m": 62.8, "wingspan_m": 60.1,
        "range_km": 14100, "cruise_speed_kmh": 903, "range_mn": 7600,
    },
}

# Mapeo rápido avion_id (CSV) → tipo de aeronave
# Flota real: 6 A380 (IDs 1-6), 18 B777 (7-24), 11 A350 (25-35), 15 B787 (36-50)
def aircraft_type_for_id(avion_id: int) -> str:
    if avion_id <= 6:    return "A380"
    elif avion_id <= 24: return "B777"
    elif avion_id <= 35: return "A350"
    else:                return "B787"
