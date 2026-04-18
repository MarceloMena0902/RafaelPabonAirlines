"""
models/schemas.py
─────────────────
Modelos Pydantic para validación de requests/responses en FastAPI.
Separados de la lógica de BD para mantener capas limpias.
"""
from datetime import date, time, datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator


# =============================================================
#  Aeropuerto
# =============================================================
class Airport(BaseModel):
    code:      str
    name:      str
    city:      str
    country:   str
    latitude:  float
    longitude: float


# =============================================================
#  Aeronave
# =============================================================
class Aircraft(BaseModel):
    id:                 int
    type_code:          str
    manufacturer:       str
    model:              str
    first_class_seats:  int
    economy_seats:      int
    engines:            str
    length_m:           float
    wingspan_m:         float
    range_km:           int
    cruise_speed_kmh:   int
    range_mn:           int


# =============================================================
#  Vuelo
# =============================================================
class FlightBase(BaseModel):
    flight_date:        date
    departure_time:     time
    origin:             str
    destination:        str
    aircraft_id:        int
    status:             str
    gate:               str
    price_economy:      float
    price_first:        float
    duration_hours:     int
    available_economy:  int
    available_first:    int
    node_owner:         str


class FlightResponse(FlightBase):
    id: int


class FlightSearchRequest(BaseModel):
    origin:       Optional[str] = None
    destination:  Optional[str] = None
    flight_date:  Optional[date] = None
    cabin_class:  Optional[str] = "ECONOMY"   # ECONOMY | FIRST


# =============================================================
#  Pasajero
# =============================================================
class PassengerBase(BaseModel):
    passport:    str
    full_name:   str
    nationality: str
    email:       str
    home_region: Optional[str] = None


class PassengerResponse(PassengerBase):
    created_at: Optional[datetime] = None


# =============================================================
#  Reserva
# =============================================================
class ReservationRequest(BaseModel):
    flight_id:          int
    passenger_passport: str
    seat_number:        str
    cabin_class:        str    # ECONOMY | FIRST
    status:             Optional[str] = "CONFIRMED"  # CONFIRMED | RESERVED
    buyer_node:         Optional[str] = None  # nodo desde donde compra el usuario

    @field_validator("cabin_class")
    @classmethod
    def validate_cabin(cls, v: str) -> str:
        if v not in ("ECONOMY", "FIRST"):
            raise ValueError("cabin_class debe ser ECONOMY o FIRST")
        return v


class ReservationResponse(BaseModel):
    id:                 int
    transaction_id:     str
    flight_id:          int
    passenger_passport: str
    seat_number:        str
    cabin_class:        str
    status:             str
    price_paid:         float
    node_origin:        str
    vector_clock:       str
    created_at:         Optional[datetime] = None


class CancelRequest(BaseModel):
    transaction_id: str


# =============================================================
#  Estado de nodos
# =============================================================
class NodeStatusResponse(BaseModel):
    node:             str
    is_online:        bool
    vector_clock:     dict
    blocked_airports: list[str]


class SystemStatusResponse(BaseModel):
    nodes:                list[NodeStatusResponse]
    all_blocked_airports: list[str]
    service_message:      Optional[str] = None
