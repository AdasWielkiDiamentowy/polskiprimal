"""Storage abstraction (Requirement 2).

Import from here in services: ``from app.storage import StorageBackend, NotFound``.
Obtain the configured backend with ``get_storage_backend()`` (selected by the
``STORAGE_BACKEND`` setting). boto3 lives only in ``app.storage.s3`` and is loaded lazily.
"""

from app.storage.base import NotFound, ReserveResult, StorageBackend, StorageError
from app.storage.factory import (
    StorageConfigError,
    create_storage_backend,
    get_storage_backend,
)
from app.storage.memory import InMemoryStorageBackend

__all__ = [
    "InMemoryStorageBackend",
    "NotFound",
    "ReserveResult",
    "StorageBackend",
    "StorageConfigError",
    "StorageError",
    "create_storage_backend",
    "get_storage_backend",
]
