"""User account model (Requirement 4.6: exactly one role per user)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr

Role = Literal["consumer", "supplier", "admin"]


class User(BaseModel):
    id: str  # uuid
    email: EmailStr
    password_hash: str
    role: Role
    display_name: str
    verified_farmer: bool = False  # admin-controlled (R6.5)
    created_at: datetime
