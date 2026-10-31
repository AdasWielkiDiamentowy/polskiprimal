"""Abstract storage boundary (Requirement 2).

Every feature (routers, services) depends on :class:`StorageBackend` and never on
S3/boto3 directly. Phase 1 ships an S3 implementation; Option B (DynamoDB) and Option C
(PostgreSQL) add new subclasses behind the same interface, with no feature rewrite.
"""

from __future__ import annotations

import posixpath
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

RESERVATIONS_PREFIX = "reservations/"


class StorageError(Exception):
    """Base class for storage errors."""


class NotFound(StorageError, KeyError):
    """Raised by :meth:`StorageBackend.get_json` when the key does not exist (R2.5).

    Subclasses ``KeyError`` so generic lookups can catch it too, but callers should
    catch ``NotFound`` explicitly.
    """

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key

    def __str__(self) -> str:  # KeyError would otherwise repr() the key
        return f"Object not found: {self.key}"


@dataclass(frozen=True)
class ReserveResult:
    """Outcome of :meth:`StorageBackend.try_reserve`.

    - ``ok``: whether the request was accepted.
    - ``status``: reservation status on success (Phase 1: ``"requested"``); ``None`` when
      rejected.
    - ``reason``: machine-readable rejection reason when ``ok`` is False
      (e.g. ``"slot_not_found"``; Option B/C may add ``"insufficient_stock"``).
    - ``reservation_id`` / ``key``: identify the stored reservation object on success.
    """

    ok: bool
    status: str | None = None
    reason: str | None = None
    reservation_id: str | None = None
    key: str | None = None


def slot_id_from_key(slot_key: str) -> str:
    """``calendar/slots/abc.json`` -> ``abc``."""
    name = posixpath.basename(slot_key)
    return name[:-5] if name.endswith(".json") else name


def reservation_key(slot_id: str, reservation_id: str) -> str:
    return f"{RESERVATIONS_PREFIX}{slot_id}/{reservation_id}.json"


class StorageBackend(ABC):
    """Abstract JSON object store. Keys are ``/``-separated strings (S3-style)."""

    @abstractmethod
    async def get_json(self, key: str) -> dict:
        """Return the JSON object at ``key``. Raises :class:`NotFound` if missing."""

    @abstractmethod
    async def put_json(self, key: str, value: dict) -> None:
        """Create or overwrite the JSON object at ``key``."""

    @abstractmethod
    async def list(self, prefix: str) -> list[str]:
        """Return all object keys starting with ``prefix``, sorted ascending."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete ``key``. Deleting a missing key is a no-op (S3 semantics)."""

    @abstractmethod
    async def try_reserve(self, slot_key: str, request: dict) -> ReserveResult:
        """Attempt a reservation against the slot stored at ``slot_key``.

        Phase 1 (Option A) contract: if the slot is missing, return
        ``ReserveResult(ok=False, reason="slot_not_found")`` (never raise). Otherwise store
        a reservation-request object at ``reservations/{slot_id}/{reservation_id}.json``
        with ``status="requested"`` and leave the slot's quantity unchanged (R8.2).

        Expiry (slot date in the past) is checked by the reservation service, not here,
        so the storage layer stays free of business/time rules.

        Option B/C implementations keep this signature but deduct stock atomically and
        may return ``ok=False, reason="insufficient_stock"``.
        """

    async def _record_reservation_request(
        self, slot_key: str, request: dict
    ) -> ReserveResult:
        """Phase 1 request-only reservation built on get/put.

        Shared by Option A backends (in-memory fake, S3). Safe without locking because it
        only writes a new, uniquely keyed object and never modifies the slot.
        """
        try:
            await self.get_json(slot_key)
        except NotFound:
            return ReserveResult(ok=False, reason="slot_not_found")

        slot_id = slot_id_from_key(slot_key)
        reservation_id = str(request.get("id") or uuid.uuid4().hex)
        record: dict[str, Any] = dict(request)
        record["id"] = reservation_id
        record["slot_id"] = slot_id
        record["status"] = "requested"
        record.setdefault("created_at", datetime.now(timezone.utc).isoformat())

        key = reservation_key(slot_id, reservation_id)
        await self.put_json(key, record)
        return ReserveResult(
            ok=True, status="requested", reservation_id=reservation_id, key=key
        )
