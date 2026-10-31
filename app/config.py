"""Application configuration via pydantic-settings.

Reads from environment variables and an optional `.env` file. The app MUST start
even when optional configuration (payment keys, database URL, AWS credentials) is
absent (Requirement 1.5). Only the storage variables for the selected backend are
required later — not during scaffolding — so nothing here is mandatory.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings.

    All fields have safe defaults or are optional so the application boots with no
    `.env` present. This keeps the "fast launch / in progress" experience working
    (Requirements 1.1, 1.5).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # tolerate unknown/future env vars without crashing
    )

    # --- Core app ---
    APP_ENV: Literal["dev", "prod"] = "dev"
    SECRET_KEY: str = "dev-insecure-change-me"
    BASE_URL: str = "http://localhost:8000"

    # --- Storage selection: "s3" (default) or "memory" (dev/tests). See app/storage/factory.py ---
    STORAGE_BACKEND: str = "s3"

    # --- S3 storage. Optional at startup; S3_BUCKET and AWS_REGION are required (checked
    # lazily, with a clear error) the first time the s3 backend is built. Credentials may
    # be omitted to use the default AWS chain (IAM role). ---
    S3_BUCKET: str | None = None
    AWS_REGION: str | None = None
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    S3_ENDPOINT_URL: str | None = None  # e.g. local MinIO in dev

    # --- Optional future vars — absence must never break startup (R1.5) ---
    DATABASE_URL: str | None = None
    BLIK_API_KEY: str | None = None
    PRZELEWY24_MERCHANT_ID: str | None = None
    PRZELEWY24_API_KEY: str | None = None

    @property
    def is_prod(self) -> bool:
        return self.APP_ENV == "prod"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (one load per process)."""
    return Settings()
