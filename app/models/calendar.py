"""Calendar and reservation models (Requirements 6-8)."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel


class AvailabilitySlot(BaseModel):
    id: str
    supplier_id: str
    product: str
    quantity: float
    unit: str  # kg, szt, etc.
    market_location: str
    date: date
    time_start: time
    time_end: time
    price: float | None = None
    notes: str = ""
    verified_farmer: bool = False


class Reservation(BaseModel):
    id: str
    slot_id: str
    consumer_ref: str  # name/phone/email or user id
    quantity: float
    status: Literal["requested", "confirmed", "declined"] = "requested"
    created_at: datetime
