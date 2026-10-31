"""Pydantic data models serialized to/from JSON.

Field names are chosen so the same shapes can later map onto DB tables (Option C).
"""

from app.models.calendar import AvailabilitySlot, Reservation
from app.models.content import BlogPost, Category
from app.models.theme import ThemeConfig
from app.models.user import Role, User

__all__ = [
    "AvailabilitySlot",
    "BlogPost",
    "Category",
    "Reservation",
    "Role",
    "ThemeConfig",
    "User",
]
