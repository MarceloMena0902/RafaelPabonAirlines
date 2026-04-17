"""
geo/proximity.py
────────────────
Calcula dinámicamente qué aeropuertos quedan "bajo responsabilidad"
de cada nodo regional usando distancia geodésica real (geopy).

Lógica (Voronoi geográfico):
  Para cada aeropuerto, encontrar el nodo cuya ciudad central
  esté más cerca. Ese nodo es el "dueño" del aeropuerto.

Cuando un nodo cae, todos los aeropuertos que le pertenecen
se marcan como no disponibles para ventas.
"""
from functools import lru_cache
from geopy.distance import geodesic

# Coordenadas de las ciudades sede de cada nodo
NODE_CENTERS: dict[str, tuple[float, float]] = {
    "beijing": (39.9042, 116.4074),   # Beijing, China
    "ukraine": (50.4501,  30.5234),   # Kyiv, Ukraine
    "lapaz":   (-16.4897, -68.1193),  # La Paz, Bolivia
}

# Coordenadas de los 15 aeropuertos del sistema
AIRPORT_COORDS: dict[str, tuple[float, float]] = {
    "ATL": (33.6407,  -84.4277),
    "PEK": (40.0801,  116.5846),
    "DXB": (25.2532,   55.3657),
    "TYO": (35.5494,  139.7798),
    "LON": (51.4775,   -0.4614),
    "LAX": (33.9425, -118.4081),
    "PAR": (49.0097,    2.5479),
    "FRA": (50.0379,    8.5622),
    "IST": (41.2608,   28.7418),
    "SIN": ( 1.3644,  103.9915),
    "MAD": (40.4983,   -3.5676),
    "AMS": (52.3086,    4.7639),
    "DFW": (32.8998,  -97.0403),
    "CAN": (23.3959,  113.3080),
    "SAO": (-23.4356, -46.4731),
}


@lru_cache(maxsize=1)
def build_airport_node_map() -> dict[str, str]:
    """
    Devuelve un dict {airport_code: node_name} donde node_name
    es el nodo geográficamente más cercano a ese aeropuerto.

    Resultado cacheado (los aeropuertos no cambian en runtime).
    """
    mapping: dict[str, str] = {}
    for code, coords in AIRPORT_COORDS.items():
        distances = {
            node: geodesic(coords, center).km
            for node, center in NODE_CENTERS.items()
        }
        nearest = min(distances, key=distances.get)
        mapping[code] = nearest
    return mapping


def airports_for_node(node_name: str) -> list[str]:
    """Devuelve los códigos de aeropuerto asignados a un nodo."""
    mapping = build_airport_node_map()
    return [code for code, owner in mapping.items() if owner == node_name]


def node_for_airport(airport_code: str) -> str:
    """Devuelve el nodo responsable de un aeropuerto dado."""
    return build_airport_node_map().get(airport_code, "lapaz")


def blocked_airports(offline_nodes: list[str]) -> list[str]:
    """
    Dado un listado de nodos caídos, devuelve todos los códigos
    de aeropuerto que deben bloquear ventas.

    Se llama en cada request para mostrar el banner de
    'Servicio no disponible en esta región'.
    """
    blocked: set[str] = set()
    for node in offline_nodes:
        blocked.update(airports_for_node(node))
    return list(blocked)


def distances_from_node(node_name: str) -> dict[str, float]:
    """
    Devuelve la distancia en km desde el nodo dado a cada aeropuerto.
    Útil para debug y para el frontend (mostrar región afectada).
    """
    center = NODE_CENTERS[node_name]
    return {
        code: round(geodesic(coords, center).km, 1)
        for code, coords in AIRPORT_COORDS.items()
    }
