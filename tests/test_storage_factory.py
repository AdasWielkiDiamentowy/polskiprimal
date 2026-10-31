"""Backend selection from config (R2.4, R2.6) and the boto3 isolation rule (R2.2)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.config import Settings
from app.storage import (
    InMemoryStorageBackend,
    StorageConfigError,
    create_storage_backend,
)
from app.storage.s3 import S3StorageBackend


def make_settings(**overrides) -> Settings:
    # _env_file=None: never read a developer's real .env during tests.
    return Settings(_env_file=None, **overrides)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in (
        "STORAGE_BACKEND",
        "S3_BUCKET",
        "AWS_REGION",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "S3_ENDPOINT_URL",
    ):
        monkeypatch.delenv(var, raising=False)


def test_memory_backend_selected():
    backend = create_storage_backend(make_settings(STORAGE_BACKEND="memory"))
    assert isinstance(backend, InMemoryStorageBackend)


def test_s3_backend_selected_with_minio_endpoint():
    backend = create_storage_backend(
        make_settings(
            STORAGE_BACKEND="s3",
            S3_BUCKET="b",
            AWS_REGION="eu-central-1",
            AWS_ACCESS_KEY_ID="k",
            AWS_SECRET_ACCESS_KEY="s",
            S3_ENDPOINT_URL="http://localhost:9000",
        )
    )
    assert isinstance(backend, S3StorageBackend)
    assert backend.bucket == "b"
    assert backend._client.meta.endpoint_url == "http://localhost:9000"


def test_s3_without_explicit_credentials_is_allowed():
    backend = create_storage_backend(
        make_settings(STORAGE_BACKEND="s3", S3_BUCKET="b", AWS_REGION="eu-central-1")
    )
    assert isinstance(backend, S3StorageBackend)


def test_s3_missing_required_settings_fails_fast_with_clear_message():
    with pytest.raises(StorageConfigError) as exc_info:
        create_storage_backend(make_settings(STORAGE_BACKEND="s3"))
    message = str(exc_info.value)
    assert "S3_BUCKET" in message and "AWS_REGION" in message


def test_s3_half_configured_credentials_rejected():
    with pytest.raises(StorageConfigError, match="AWS_SECRET_ACCESS_KEY"):
        create_storage_backend(
            make_settings(
                S3_BUCKET="b", AWS_REGION="eu-central-1", AWS_ACCESS_KEY_ID="k"
            )
        )


@pytest.mark.parametrize("name", ["dynamodb", "postgres", "nope"])
def test_unsupported_backend_names_rejected(name):
    with pytest.raises(StorageConfigError, match=name):
        create_storage_backend(make_settings(STORAGE_BACKEND=name))


def test_boto3_is_only_imported_in_s3_backend_module():
    """R2.2: routes/services/templates must never use boto3 directly."""
    app_dir = Path(__file__).resolve().parent.parent / "app"
    import_re = re.compile(r"^\s*(?:import|from)\s+(?:boto3|botocore)\b", re.MULTILINE)
    offenders = [
        p.relative_to(app_dir).as_posix()
        for p in app_dir.rglob("*.py")
        if p.relative_to(app_dir).as_posix() != "storage/s3.py"
        and import_re.search(p.read_text(encoding="utf-8"))
    ]
    assert offenders == []
