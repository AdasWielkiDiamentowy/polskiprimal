"""Run the shared StorageBackend contract against the in-memory fake."""

from __future__ import annotations

import pytest

from app.storage import InMemoryStorageBackend
from tests.storage_contract import StorageBackendContract


class TestInMemoryStorageBackend(StorageBackendContract):
    @pytest.fixture
    def backend(self) -> InMemoryStorageBackend:
        return InMemoryStorageBackend()

    @pytest.mark.anyio
    async def test_rejects_non_json_values(self, backend):
        with pytest.raises(TypeError):
            await backend.put_json("x.json", {"bad": object()})
