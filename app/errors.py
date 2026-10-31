"""Global exception handlers (design.md "Error Handling").

- ``NotFound`` from the storage layer and any HTTP 404 -> the Polish 404 page (R3.7).
- Other ``StorageError`` (e.g. storage not configured, S3 unreachable) -> a friendly 503
  page. Neither case ever surfaces as an unhandled 500.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler as default_http_handler
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.storage.base import NotFound, StorageError
from app.templating import render_page

logger = logging.getLogger(__name__)


async def _render_404(request: Request):
    return await render_page(request, "404.html", {"title": "Nie znaleziono strony"}, status_code=404)


async def not_found_handler(request: Request, exc: NotFound):
    return await _render_404(request)


async def storage_error_handler(request: Request, exc: StorageError):
    logger.error("Storage error on %s: %s", request.url.path, exc)
    return await render_page(
        request, "error.html", {"title": "Treść chwilowo niedostępna"}, status_code=503
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return await _render_404(request)
    return await default_http_handler(request, exc)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(NotFound, not_found_handler)
    app.add_exception_handler(StorageError, storage_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
