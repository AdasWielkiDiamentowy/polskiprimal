"""Jinja2 templating setup and the shared page renderer.

:func:`render_page` loads the theme through the StorageBackend on every render and injects
it as CSS custom properties in the base layout (Requirements 9.1-9.3). If storage is
unavailable it falls back to the default theme, so error pages can always render.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from app.deps import get_storage
from app.models.theme import ThemeConfig
from app.services.content_service import render_markdown
from app.services.theme_service import ThemeService, theme_css
from app.storage.base import StorageError

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_MONTHS_GENITIVE = [
    "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
    "lipca", "sierpnia", "września", "października", "listopada", "grudnia",
]  # fmt: skip


def pl_date(value: date | datetime | None) -> str:
    """``2025-06-05`` -> ``5 czerwca 2025``; empty string for ``None``."""
    if value is None:
        return ""
    return f"{value.day} {_MONTHS_GENITIVE[value.month - 1]} {value.year}"


def markdown_filter(text: str | None) -> Markup:
    """Render trusted, team-authored Markdown (see ``render_markdown``)."""
    return Markup(render_markdown(text or ""))


TAILWIND_CSS = Path(__file__).resolve().parent / "static" / "css" / "tailwind.css"


def tailwind_css_url() -> str | None:
    """URL of the compiled Tailwind stylesheet, or ``None`` if it has not been built.

    The Docker image builds it (``npm run build:css``). Without it (plain local dev) the
    layout falls back to the Tailwind CDN script. The mtime query string busts caches
    after a rebuild.
    """
    try:
        return f"/static/css/tailwind.css?v={int(TAILWIND_CSS.stat().st_mtime)}"
    except OSError:
        return None


templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["site_name"] = "polskiprimal.pl"
templates.env.globals["tailwind_css_url"] = tailwind_css_url
templates.env.filters["pl_date"] = pl_date
templates.env.filters["markdown"] = markdown_filter


async def _load_theme_css(request: Request) -> str:
    try:
        theme = await ThemeService(get_storage(request)).get_theme()
    except StorageError:
        logger.warning("Storage unavailable; rendering with default theme", exc_info=True)
        theme = ThemeConfig()
    return theme_css(theme)


async def render_page(
    request: Request,
    template_name: str,
    context: dict[str, Any] | None = None,
    *,
    status_code: int = 200,
):
    """Render ``template_name`` with the current theme injected."""
    ctx = dict(context or {})
    ctx.setdefault("theme_css", await _load_theme_css(request))
    return templates.TemplateResponse(request, template_name, ctx, status_code=status_code)
