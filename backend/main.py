"""
main.py
───────
Punto de entrada de la aplicación FastAPI.

Lifecycle:
  • startup  → arranca el loop de sincronización entre nodos
               y hace el primer healthcheck.
  • shutdown → cancela el loop.

Estructura de rutas:
  /flights       → búsqueda y detalle de vuelos
  /reservations  → crear y cancelar reservas
  /passengers    → consulta de pasajeros
  /nodes         → estado del sistema distribuido
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import flights, reservations, passengers, nodes, tickets
from sync.synchronizer import run_sync_loop, check_node_health

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

_sync_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────
    logger.info("Iniciando RafaelPabonAirlines API...")
    logger.info("Ejecutando primer healthcheck de nodos...")
    await check_node_health()

    global _sync_task
    _sync_task = asyncio.create_task(run_sync_loop())
    logger.info("Loop de sincronización iniciado.")
    yield

    # ── Shutdown ──────────────────────────────────────────────
    if _sync_task:
        _sync_task.cancel()
        try:
            await _sync_task
        except asyncio.CancelledError:
            pass
    logger.info("RafaelPabonAirlines API detenida.")


app = FastAPI(
    title="RafaelPabonAirlines API",
    description=(
        "Sistema distribuido de reservas aéreas. "
        "Arquitectura CP con Relojes Vectoriales e Identity Key Jumping. "
        "Nodos: Beijing (SQL Server) | Ucrania (SQL Server) | La Paz (MongoDB)"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS (permite peticiones desde el frontend React) ─────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────
app.include_router(flights.router)
app.include_router(reservations.router)
app.include_router(passengers.router)
app.include_router(nodes.router)
app.include_router(tickets.router)


@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "app": "RafaelPabonAirlines API v1.0.0"}
