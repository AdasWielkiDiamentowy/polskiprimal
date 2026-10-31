"""Theme configuration (Requirement 9), injected as CSS custom properties."""

from __future__ import annotations

from pydantic import BaseModel


class ThemeConfig(BaseModel):
    primary_color: str = "#2e7d32"
    accent_color: str = "#ff8f00"
    font_family: str = "Inter, system-ui, sans-serif"
