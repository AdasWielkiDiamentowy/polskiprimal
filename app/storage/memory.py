"""In-memory StorageBackend for tests and local development (no AWS needed)."""

from __future__ import annotations

import json

from app.storage.base import NotFound, ReserveResult, StorageBackend


def _validate_key(key: str) -> None:
    if not isinstance(key, str) or not key:
        raise ValueError("Storage key must be a non-empty string")


class InMemoryStorageBackend(StorageBackend):
    """Dict-backed backend.

    Values are stored as serialized JSON text, so (like S3) only JSON-serializable dicts
    are accepted and callers always receive fresh copies that cannot mutate stored state.
    """

    def __init__(self) -> None:
        self._objects: dict[str, str] = {}

    async def get_json(self, key: str) -> dict:
        _validate_key(key)
        try:
            raw = self._objects[key]
        except KeyError:
            raise NotFound(key) from None
        return json.loads(raw)

    async def put_json(self, key: str, value: dict) -> None:
        _validate_key(key)
        if not isinstance(value, dict):
            raise TypeError("put_json value must be a dict")
        self._objects[key] = json.dumps(value, ensure_ascii=False)

    async def list(self, prefix: str) -> list[str]:
        return sorted(k for k in self._objects if k.startswith(prefix))

    async def delete(self, key: str) -> None:
        _validate_key(key)
        self._objects.pop(key, None)

    async def try_reserve(self, slot_key: str, request: dict) -> ReserveResult:
        return await self._record_reservation_request(slot_key, request)
