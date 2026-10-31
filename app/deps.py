"""Shared request-level dependencies.

Routes obtain storage only through :func:`get_storage`; they never build backends or touch
boto3 (Requirement 2.2). ``create_app(storage=...)`` can inject a backend (used by tests);
otherwise the backend selected by ``STORAGE_BACKEND`` is used.
"""

from __future__ import annotations

from fastapi import Request

from app.storage.base import StorageBackend
from app.storage.factory import get_storage_backend


def get_storage(request: Request) -> StorageBackend:
    """The StorageBackend for this app. May raise ``StorageError`` if misconfigured."""
    injected = getattr(request.app.state, "storage", None)
    if injected is not None:
        return injected
    return get_storage_backend()
