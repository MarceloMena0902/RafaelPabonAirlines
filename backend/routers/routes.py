"""
routers/routes.py
─────────────────────────────────────────────────────────────────
Algoritmos de selección de rutas:

  GET /routes/shortest   Dijkstra — ruta de menor costo entre 2 aeropuertos
  GET /routes/tour       TSP (Held-Karp DP) — tour óptimo multi-ciudad

Usa las matrices de precios / tiempos de data/matrices.py como grafo.
"""
import heapq
import math
from itertools import permutations
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from data.matrices import PRICES_ECONOMY, PRICES_FIRST, FLIGHT_HOURS

router = APIRouter(prefix="/routes", tags=["Rutas"])

AIRPORTS = sorted(PRICES_ECONOMY.keys())   # 14 aeropuertos


# ── Helpers ───────────────────────────────────────────────────

def _price_matrix(cabin: str) -> dict:
    return PRICES_FIRST if cabin == "FIRST" else PRICES_ECONOMY


def _edge_weight(src: str, dst: str, cabin: str) -> Optional[float]:
    """Costo directo src→dst, None si no hay vuelo."""
    m = _price_matrix(cabin)
    if src not in m or dst not in m[src]:
        return None
    v = m[src][dst]
    return float(v) if (v is not None and v > 0) else None


# ══════════════════════════════════════════════════════════════
#  DIJKSTRA — ruta de menor costo
# ══════════════════════════════════════════════════════════════

def dijkstra(origin: str, destination: str, cabin: str):
    """
    Retorna la ruta de menor costo entre origin y destination.
    Permite escalas usando todos los aeropuertos del grafo.

    Returns dict:
      { path: ["ATL","LON","PEK"], total_cost: 1600, total_hours: 17, hops: 1 }
    """
    if origin not in AIRPORTS:
        raise HTTPException(400, f"Aeropuerto origen '{origin}' no reconocido. Válidos: {AIRPORTS}")
    if destination not in AIRPORTS:
        raise HTTPException(400, f"Aeropuerto destino '{destination}' no reconocido. Válidos: {AIRPORTS}")
    if origin == destination:
        raise HTTPException(400, "Origen y destino son iguales.")

    # dist[node] = (costo_acumulado, horas_acumuladas, ruta[])
    INF = math.inf
    dist  = {a: INF for a in AIRPORTS}
    prev  = {a: None for a in AIRPORTS}
    hours = {a: INF for a in AIRPORTS}
    dist[origin] = 0.0
    hours[origin] = 0.0

    # heap: (costo, nodo, ruta, horas)
    heap = [(0.0, origin, [origin], 0.0)]

    while heap:
        cost, node, path, h = heapq.heappop(heap)
        if cost > dist[node]:
            continue
        if node == destination:
            return {
                "path":        path,
                "total_cost":  round(cost, 2),
                "total_hours": round(h, 1),
                "hops":        len(path) - 2,
                "cabin":       cabin,
                "segments":    [
                    {
                        "from": path[i],
                        "to":   path[i+1],
                        "cost": round(_edge_weight(path[i], path[i+1], cabin) or 0, 2),
                        "hours": FLIGHT_HOURS.get(path[i], {}).get(path[i+1], 0),
                    }
                    for i in range(len(path) - 1)
                ],
            }
        for neighbor in AIRPORTS:
            if neighbor in path:   # evitar ciclos
                continue
            w = _edge_weight(node, neighbor, cabin)
            if w is None:
                continue
            new_cost = cost + w
            fh = FLIGHT_HOURS.get(node, {}).get(neighbor, 0)
            new_h = h + fh
            if new_cost < dist[neighbor]:
                dist[neighbor] = new_cost
                hours[neighbor] = new_h
                heapq.heappush(heap, (new_cost, neighbor, path + [neighbor], new_h))

    raise HTTPException(404, f"No existe ruta de {origin} a {destination} con clase {cabin}.")


# ══════════════════════════════════════════════════════════════
#  TSP — Held-Karp DP (tour óptimo multi-ciudad)
# ══════════════════════════════════════════════════════════════

def tsp_held_karp(cities: list[str], cabin: str):
    """
    TSP con programación dinámica (Held-Karp).
    Devuelve el tour de menor costo que visita todos las ciudades
    y regresa al origen.

    Solo funciona bien con ≤ 12 ciudades (complejidad O(n²·2ⁿ)).
    """
    n = len(cities)
    if n < 2:
        raise HTTPException(400, "Se necesitan al menos 2 ciudades.")
    if n > 12:
        raise HTTPException(400, "Máximo 12 ciudades para TSP exacto.")

    # Construir matriz de distancias entre las ciudades dadas
    # (usando Dijkstra para pares sin vuelo directo)
    INF = math.inf
    cost_mat = [[INF] * n for _ in range(n)]
    path_mat = [[None] * n for _ in range(n)]

    for i in range(n):
        for j in range(n):
            if i == j:
                cost_mat[i][j] = 0
                path_mat[i][j] = [cities[i]]
                continue
            try:
                r = dijkstra(cities[i], cities[j], cabin)
                cost_mat[i][j] = r["total_cost"]
                path_mat[i][j] = r["path"]
            except HTTPException:
                pass   # sin ruta → INF

    # Held-Karp DP
    # dp[mask][i] = costo mínimo de haber visitado los nodos en mask,
    #               terminando en el nodo i (empezando desde 0).
    dp   = [[INF] * n for _ in range(1 << n)]
    par  = [[-1]  * n for _ in range(1 << n)]
    dp[1][0] = 0   # partimos del primer ciudad (índice 0)

    for mask in range(1 << n):
        for u in range(n):
            if not (mask & (1 << u)):
                continue
            if dp[mask][u] == INF:
                continue
            for v in range(n):
                if mask & (1 << v):
                    continue
                new_mask = mask | (1 << v)
                new_cost = dp[mask][u] + cost_mat[u][v]
                if new_cost < dp[new_mask][v]:
                    dp[new_mask][v] = new_cost
                    par[new_mask][v] = u

    # Reconstruir solución: volver al origen
    full_mask = (1 << n) - 1
    best_cost = INF
    last_node = -1
    for u in range(1, n):
        c = dp[full_mask][u] + cost_mat[u][0]
        if c < best_cost:
            best_cost = c
            last_node = u

    if best_cost == INF:
        raise HTTPException(404, "No existe tour completo con las ciudades dadas.")

    # Reconstruir orden de ciudades
    order = []
    mask  = full_mask
    node  = last_node
    while node != -1:
        order.append(node)
        prev_node = par[mask][node]
        mask ^= (1 << node)
        node = prev_node
    order.reverse()
    order.append(0)   # regresar al origen

    city_order = [cities[i] for i in order]

    # Construir segmentos detallados
    segments = []
    for k in range(len(city_order) - 1):
        src, dst = city_order[k], city_order[k+1]
        si = cities.index(src)
        di = cities.index(dst)
        segments.append({
            "from":  src,
            "to":    dst,
            "cost":  round(cost_mat[si][di], 2),
            "path":  path_mat[si][di],
            "hops":  len(path_mat[si][di]) - 2 if path_mat[si][di] else 0,
        })

    return {
        "cities":      city_order,
        "total_cost":  round(best_cost, 2),
        "cabin":       cabin,
        "segments":    segments,
        "algorithm":   "Held-Karp TSP",
    }


# ══════════════════════════════════════════════════════════════
#  Endpoints
# ══════════════════════════════════════════════════════════════

@router.get("/shortest")
async def get_shortest_route(
    origin:      str = Query(..., description="Código aeropuerto origen  (ej: ATL)"),
    destination: str = Query(..., description="Código aeropuerto destino (ej: PEK)"),
    cabin:       str = Query("ECONOMY", description="ECONOMY | FIRST"),
):
    """
    Dijkstra: ruta de menor costo entre dos aeropuertos.
    Si no hay vuelo directo encuentra la mejor combinación de escalas.

    Aeropuertos disponibles: ATL, PEK, DXB, TYO, LON, LAX, PAR, FRA,
                              IST, SIN, MAD, AMS, DFW, CAN, SAO
    """
    return dijkstra(origin.upper(), destination.upper(), cabin.upper())


@router.get("/tour")
async def get_optimal_tour(
    cities: str = Query(..., description="Lista de aeropuertos separados por coma (ej: ATL,LON,DXB,TYO)"),
    cabin:  str = Query("ECONOMY", description="ECONOMY | FIRST"),
):
    """
    Held-Karp TSP: orden óptimo para visitar todas las ciudades
    y regresar al origen con el menor costo total.

    Máximo 12 ciudades. El tour siempre empieza y termina en la primera ciudad.
    """
    city_list = [c.strip().upper() for c in cities.split(",") if c.strip()]
    for c in city_list:
        if c not in AIRPORTS:
            raise HTTPException(400, f"Aeropuerto '{c}' no reconocido. Válidos: {AIRPORTS}")
    return tsp_held_karp(city_list, cabin.upper())


@router.get("/airports")
async def list_airports():
    """Lista de aeropuertos con rutas directas disponibles."""
    result = []
    for ap in AIRPORTS:
        directs = [dst for dst, v in PRICES_ECONOMY.get(ap, {}).items() if v]
        result.append({"code": ap, "direct_routes": sorted(directs)})
    return result
