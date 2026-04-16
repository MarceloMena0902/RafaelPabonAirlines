from datetime import date, time, datetime
from typing import Optional
from pydantic import BaseModel, field_validator


class ReservationRequest(BaseModel):
    flight_id:          int
    passenger_passport: str
    seat_number:        str
    cabin_class:        str

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
