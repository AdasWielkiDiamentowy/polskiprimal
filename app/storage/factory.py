"""Select the StorageBackend implementation from configuration (Requirements 2.4, 2.6).

Feature code obtains storage through :func:`get_storage_backend` (usable as a FastAPI
dependency) and never constructs backends or touches boto3 itself.

Backends are created lazily, so the app still boots without optional env vars (R1.5).
Selecting a backend whose required settings are missing fails fast, with a message naming
exactly which variables to set.
"""

from __future__ import annotations

from functools import lru_cache

from app.config import Settings, get_settings
from app.storage.base import StorageBackend, StorageError
from app.storage.memory import InMemoryStorageBackend


class StorageConfigError(StorageError):
    """Storage is misconfigured (unknown backend or missing required settings)."""


# Names accepted by STORAGE_BACKEND. Option B/C names are reserved for later phases.
SUPPORTED_BACKENDS = ("s3", "memory")
_FUTURE_BACKENDS = ("dynamodb", "postgres")


def create_storage_backend(settings: Settings) -> StorageBackend:
    """Build the backend named by ``settings.STORAGE_BACKEND``."""
    name = (settings.STORAGE_BACKEND or "").strip().lower()

    if name == "memory":
        # Data is lost on restart; for local development and tests only.
        return InMemoryStorageBackend()

    if name == "s3":
        missing = [
            var
            for var, value in (
                ("S3_BUCKET", settings.S3_BUCKET),
                ("AWS_REGION", settings.AWS_REGION),
            )
            if not value
        ]
        if missing:
            raise StorageConfigError(
                "STORAGE_BACKEND=s3 requires these environment variables: "
                + ", ".join(missing)
                + ". Set them in .env (see .env.example)."
            )
        if bool(settings.AWS_ACCESS_KEY_ID) != bool(settings.AWS_SECRET_ACCESS_KEY):
            raise StorageConfigError(
                "Set both AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY, or neither "
                "(to use an IAM role / default AWS credential chain)."
            )

        # Imported here so boto3 is only loaded when S3 is actually selected.
        from app.storage.s3 import S3StorageBackend

        return S3StorageBackend(
            bucket=settings.S3_BUCKET,
            region=settings.AWS_REGION,
            access_key_id=settings.AWS_ACCESS_KEY_ID or None,
            secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
            endpoint_url=settings.S3_ENDPOINT_URL or None,
        )

    if name in _FUTURE_BACKENDS:
        raise StorageConfigError(
            f"STORAGE_BACKEND={name} is not implemented yet (planned for Option B/C). "
            f"Use one of: {', '.join(SUPPORTED_BACKENDS)}."
        )
    raise StorageConfigError(
        f"Unknown STORAGE_BACKEND '{settings.STORAGE_BACKEND}'. "
        f"Use one of: {', '.join(SUPPORTED_BACKENDS)}."
    )


@lru_cache
def get_storage_backend() -> StorageBackend:
    """Process-wide backend instance; also usable as a FastAPI ``Depends`` target."""
    return create_storage_backend(get_settings())
