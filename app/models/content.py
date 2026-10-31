"""Editorial content models: categories (multi-level) and blog posts/topics."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Category(BaseModel):
    id: str
    slug: str
    title: str
    parent_id: str | None = None  # multi-level tree (R3.1)
    order: int = 0
    description_md: str = ""


class BlogPost(BaseModel):
    """A blog post, also used as a Chapter/Topic when ``category_id`` is set."""

    id: str
    slug: str
    title: str
    category_id: str | None = None
    body_md: str  # Markdown (R3.3)
    author: str
    status: Literal["draft", "published"] = "draft"  # (R3.5)
    published_at: datetime | None = None
