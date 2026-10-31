"""Theme service: load ``config/theme.json`` via the StorageBackend (Requirements 9.1-9.3).

The theme is read on every page render (no caching) so edits to ``config/theme.json``
show up on the next request without a redeploy (R9.3).

Values are authored by the team, but they end up inside a ``<style>`` block, so each one
is validated against a conservative pattern. An invalid or missing value falls back to
the default for that field; a missing or unreadable file falls back to all defaults. The
site must never fail to render because of a bad theme file.
"""

from __future__ import annotations

import logging
import re

from app.models.theme import ThemeConfig
from app.storage.base import NotFound, StorageBackend, StorageError

logger = logging.getLogger(__name__)

THEME_KEY = "config/theme.json"

# #rgb / #rrggbb / #rrggbbaa, named colours, or rgb()/hsl() functions.
_COLOR_RE = re.compile(
    r"^(#[0-9a-fA-F]{3,8}|[a-zA-Z]{3,30}|(?:rgb|hsl)a?\([0-9.,%\s/]+\))$"
)
# Font stacks: letters, digits, spaces, commas, hyphens and quotes only.
_FONT_RE = re.compile(r"^[\w\s,'\"\-]{1,200}$")

_VALIDATORS = {
    "primary_color": _COLOR_RE,
    "accent_color": _COLOR_RE,
    "font_family": _FONT_RE,
}

# ThemeConfig field -> CSS custom property name (design.md: --primary-color, --font-family).
CSS_VARIABLES = {
    "primary_color": "--primary-color",
    "accent_color": "--accent-color",
    "font_family": "--font-family",
}


def sanitize_theme(raw: object) -> ThemeConfig:
    """Build a ThemeConfig from untrusted JSON, replacing invalid fields with defaults."""
    defaults = ThemeConfig()
    data = raw if isinstance(raw, dict) else {}
    values: dict[str, str] = {}
    for field, pattern in _VALIDATORS.items():
        candidate = data.get(field)
        if isinstance(candidate, str) and pattern.match(candidate.strip()):
            values[field] = candidate.strip()
        else:
            if field in data:
                logger.warning("Ignoring invalid theme value for %s", field)
            values[field] = getattr(defaults, field)
    return ThemeConfig(**values)


def theme_css(theme: ThemeConfig) -> str:
    """CSS ``:root`` block defining the theme custom properties.

    Safe to emit unescaped inside ``<style>``: every value was validated by
    :func:`sanitize_theme` and cannot contain ``<``, ``>``, ``;``, ``{`` or ``}``.
    """
    lines = [f"  {css_name}: {getattr(theme, field)};" for field, css_name in CSS_VARIABLES.items()]
    return ":root {\n" + "\n".join(lines) + "\n}"


class ThemeService:
    def __init__(self, storage: StorageBackend) -> None:
        self._storage = storage

    async def get_theme(self) -> ThemeConfig:
        """Current theme; defaults if the file is missing, malformed or unreadable."""
        try:
            raw = await self._storage.get_json(THEME_KEY)
        except NotFound:
            return ThemeConfig()
        except StorageError:
            logger.warning("Could not read %s; using default theme", THEME_KEY, exc_info=True)
            return ThemeConfig()
        return sanitize_theme(raw)
