"""The app must start with NO optional env vars set (Requirement 1.5).

Payment keys, DATABASE_URL, and AWS credentials being absent must never break
startup. This test clears those variables, rebuilds settings and the app from
scratch, and confirms the app boots and serves /health.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

OPTIONAL_VARS = [
    "DATABASE_URL",
    "BLIK_API_KEY",
    "PRZELEWY24_MERCHANT_ID",
    "PRZELEWY24_API_KEY",
    "S3_BUCKET",
    "AWS_REGION",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "S3_ENDPOINT_URL",
    "SECRET_KEY",
    "BASE_URL",
    "APP_ENV",
    "STORAGE_BACKEND",
]


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    """Remove every optional var and point .env lookup at an empty dir."""
    for var in OPTIONAL_VARS:
        monkeypatch.delenv(var, raising=False)
    # Run from a temp dir so no real `.env` is picked up.
    monkeypatch.chdir(tmp_path)


def test_app_starts_with_no_optional_env(clean_env):
    """Settings load and the app boots with zero optional configuration present."""
    import app.config as config_module
    import app.main as main_module

    # Reload so cached settings / module-level app are rebuilt in the clean env.
    importlib.reload(config_module)
    importlib.reload(main_module)

    config_module.get_settings.cache_clear()
    settings = config_module.get_settings()

    # Safe defaults applied; nothing required.
    assert settings.APP_ENV == "dev"
    assert settings.STORAGE_BACKEND == "s3"
    assert settings.DATABASE_URL is None
    assert settings.S3_BUCKET is None

    app = main_module.create_app()
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
