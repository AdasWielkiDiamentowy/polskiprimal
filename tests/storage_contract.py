"""Shared StorageBackend contract suite (Requirements 2.2, 2.3, 2.5).

Every backend must pass these tests. To run them against a backend, subclass
:class:`StorageBackendContract` in a ``test_*.py`` module and provide a ``backend``
fixture returning a fresh/usable instance, e.g.::

    class TestS3Backend(StorageBackendContract):
        @pytest.fixture
        def backend(self):
            return S3StorageBackend(...)

Tests write under a unique per-test prefix (``ns``) and unique slot ids, so they are safe
to run against a shared real bucket (e.g. MinIO).
"""

from __future__ import annotations

import uuid

import pytest

from app.storage import NotFound, ReserveResult, StorageBackend


@pytest.mark.anyio
class StorageBackendContract:
    @pytest.fixture
    def backend(self) -> StorageBackend:  # pragma: no cover - must be overridden
        raise NotImplementedError("Subclasses must provide a `backend` fixture")

    @pytest.fixture
    def ns(self) -> str:
        return f"contract-tests/{uuid.uuid4().hex}/"

    @pytest.fixture
    def slot_key(self) -> str:
        return f"calendar/slots/contract-{uuid.uuid4().hex}.json"

    # --- get / put -------------------------------------------------------------

    async def test_is_storage_backend(self, backend):
        assert isinstance(backend, StorageBackend)

    async def test_put_then_get_roundtrip(self, backend, ns):
        value = {
            "title": "Truskawki bez pestycydów",
            "qty": 5.5,
            "tags": ["sezonowe", "lokalne"],
            "nested": {"ok": True, "none": None},
        }
        await backend.put_json(ns + "a.json", value)
        assert await backend.get_json(ns + "a.json") == value

    async def test_put_overwrites(self, backend, ns):
        await backend.put_json(ns + "a.json", {"v": 1})
        await backend.put_json(ns + "a.json", {"v": 2})
        assert await backend.get_json(ns + "a.json") == {"v": 2}

    async def test_get_missing_raises_not_found(self, backend, ns):
        with pytest.raises(NotFound):
            await backend.get_json(ns + "missing.json")

    async def test_returned_value_is_a_copy(self, backend, ns):
        original = {"items": [1, 2], "inner": {"x": 1}}
        await backend.put_json(ns + "a.json", original)
        original["items"].append(99)  # mutate caller's input after put

        got = await backend.get_json(ns + "a.json")
        got["items"].append(3)
        got["inner"]["x"] = 42

        assert await backend.get_json(ns + "a.json") == {"items": [1, 2], "inner": {"x": 1}}

    # --- list ------------------------------------------------------------------

    async def test_list_by_prefix_sorted(self, backend, ns):
        for key in ("b/2.json", "a/1.json", "b/1.json"):
            await backend.put_json(ns + key, {"k": key})
        assert await backend.list(ns + "b/") == [ns + "b/1.json", ns + "b/2.json"]
        assert await backend.list(ns) == [
            ns + "a/1.json",
            ns + "b/1.json",
            ns + "b/2.json",
        ]

    async def test_list_empty_prefix_result(self, backend, ns):
        assert await backend.list(ns + "nothing/") == []

    # --- delete ----------------------------------------------------------------

    async def test_delete_removes_object(self, backend, ns):
        await backend.put_json(ns + "a.json", {"v": 1})
        await backend.delete(ns + "a.json")
        with pytest.raises(NotFound):
            await backend.get_json(ns + "a.json")
        assert await backend.list(ns) == []

    async def test_delete_missing_is_noop(self, backend, ns):
        await backend.delete(ns + "missing.json")  # must not raise

    # --- try_reserve (Phase 1: request -> farmer confirms) ------------------------

    async def test_try_reserve_missing_slot_returns_not_ok(self, backend, slot_key):
        result = await backend.try_reserve(slot_key, {"consumer_ref": "jan", "quantity": 5})
        assert isinstance(result, ReserveResult)
        assert result.ok is False
        assert result.reason
        slot_id = slot_key.rsplit("/", 1)[-1].removesuffix(".json")
        assert await backend.list(f"reservations/{slot_id}/") == []

    async def test_try_reserve_records_request_without_decrement(self, backend, slot_key):
        slot = {"id": "s1", "product": "Borówki", "quantity": 20.0, "unit": "kg"}
        await backend.put_json(slot_key, slot)
        slot_id = slot_key.rsplit("/", 1)[-1].removesuffix(".json")

        result = await backend.try_reserve(slot_key, {"consumer_ref": "jan", "quantity": 5})

        assert result.ok is True
        assert result.status == "requested"
        assert result.reason is None
        assert result.reservation_id
        expected_key = f"reservations/{slot_id}/{result.reservation_id}.json"
        assert result.key == expected_key
        assert await backend.list(f"reservations/{slot_id}/") == [expected_key]

        stored = await backend.get_json(expected_key)
        assert stored["status"] == "requested"
        assert stored["slot_id"] == slot_id
        assert stored["id"] == result.reservation_id
        assert stored["consumer_ref"] == "jan"
        assert stored["quantity"] == 5
        assert stored["created_at"]

        # Slot stock is NOT decremented in Phase 1 (R8.2).
        assert await backend.get_json(slot_key) == slot

        for key in await backend.list(f"reservations/{slot_id}/"):
            await backend.delete(key)
        await backend.delete(slot_key)

    async def test_try_reserve_multiple_requests_are_distinct(self, backend, slot_key):
        await backend.put_json(slot_key, {"quantity": 1})
        slot_id = slot_key.rsplit("/", 1)[-1].removesuffix(".json")

        r1 = await backend.try_reserve(slot_key, {"consumer_ref": "a", "quantity": 1})
        r2 = await backend.try_reserve(slot_key, {"consumer_ref": "b", "quantity": 1})

        assert r1.ok and r2.ok
        assert r1.reservation_id != r2.reservation_id
        assert len(await backend.list(f"reservations/{slot_id}/")) == 2

        for key in await backend.list(f"reservations/{slot_id}/"):
            await backend.delete(key)
        await backend.delete(slot_key)
