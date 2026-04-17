"""
routers/nodes.py
─────────────────
Estado del sistema distribuido y mapa Voronoi de aeropuertos.
"""
from fastapi import APIRouter, HTTPException, Query
from geo.proximity import build_airport_node_map, blocked_airports, distances_from_node
from geo.cities import search_cities, nearest_node_for_city
from sync.synchronizer import node_states, get_offline_nodes

router = APIRouter(prefix="/nodes", tags=["Nodos"])


@router.get("/status")
async def get_system_status():
    offline = get_offline_nodes()
    blocked = blocked_airports(offline)
    nodes_info = []
    for name, state in node_states.items():
        nodes_info.append({
            "node":             name,
            "is_online":        state.is_online,
            "vector_clock":     state.vector_clock.__dict__,
            "blocked_airports": blocked_airports([name]) if not state.is_online else [],
        })
    return {
        "nodes":                nodes_info,
        "all_blocked_airports": blocked,
        "service_message":      None if not offline else f"Nodos caídos: {', '.join(offline)}",
    }


@router.get("/map")
async def get_node_map():
    """Devuelve el mapa Voronoi: { airport_code: node_name }"""
    return build_airport_node_map()


@router.get("/nearest")
async def get_nearest_node(city: str = Query(..., description="Nombre de ciudad")):
    """
    Dado un nombre de ciudad, devuelve el nodo más cercano.
    Respuesta: { city, country, lat, lon, node, node_label, node_flag }
    """
    result = nearest_node_for_city(city)
    if not result:
        raise HTTPException(status_code=404, detail=f"Ciudad '{city}' no encontrada.")
    return result


@router.get("/cities/search")
async def search_world_cities(
    q: str = Query(..., min_length=1, description="Texto de búsqueda"),
    limit: int = Query(10, ge=1, le=50),
):
    """
    Busca ciudades del mundo por nombre o país.
    Devuelve lista de { city, country, lat, lon }.
    """
    return search_cities(q, limit)
