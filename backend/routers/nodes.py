"""
routers/nodes.py
─────────────────
Estado del sistema distribuido y mapa Voronoi de aeropuertos.
"""
from fastapi import APIRouter
from geo.proximity import build_airport_node_map, blocked_airports, distances_from_node
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
