"""FastAPI application factory for polskiprimal.pl (Phase 1, Option A).

`create_app()` builds and returns the FastAPI instance: loads settings, mounts
static files, registers routers and error handlers. The module also exposes a
module-level `app` so it can be run with `uvicorn app.main:app`.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.errors import register_error_handlers
from app.routers import public
from app.seed import seed_storage
from app.storage.base import StorageBackend

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(storage: StorageBackend | None = None) -> FastAPI:
    """Build and configure the FastAPI application instance.

    ``storage`` injects a backend (used by tests); by default the backend selected by
    ``STORAGE_BACKEND`` is used.
    """
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # The in-memory backend starts empty on every run, so load the starter content
        # from `content/` to give local dev real pages. S3 is never seeded automatically.
        if storage is None and settings.STORAGE_BACKEND.strip().lower() == "memory":
            from app.storage.factory import get_storage_backend

            written = await seed_storage(get_storage_backend())
            logger.info("Seeded in-memory storage with %d object(s)", len(written))
        yield

    app = FastAPI(
        title="polskiprimal.pl",
        description=(
            "Polish healthy-food / farm-to-table platform (Phase 1, Option A: "
            "FastAPI + Amazon S3, no database)."
        ),
        version="0.1.0",
        debug=not settings.is_prod,
        lifespan=lifespan,
    )
    app.state.storage = storage

    # Serve static assets (CSS/JS/images). Directory exists even if empty.
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Routers and error handlers
    app.include_router(public.router)
    register_error_handlers(app)

    return app


# Module-level instance for `uvicorn app.main:app`.
app = create_app()
