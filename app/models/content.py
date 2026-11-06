"""Editorial content models: categories (multi-level) and blog posts/topics."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Union

from pydantic import BaseModel, field_validator


class Category(BaseModel):
    id: str
    slug: str
    title: str
    parent_id: str | None = None  # multi-level tree (R3.1)
    order: int = 0
    description_md: str = ""
    image_url: str | None = None  # optional cover/thumbnail image

    @field_validator("description_md", mode="before")
    @classmethod
    def coerce_list_to_str(cls, v: Union[str, list]) -> str:
        """Accept either a plain string or a list of strings.

        A list is joined with newlines so authors can write multi-line
        descriptions as a JSON array without escaping \\n manually.
        """
        if isinstance(v, list):
            # Empty string "" = paragraph break.
            # Non-empty strings next to each other = same paragraph (joined with space).
            paragraphs: list[list[str]] = [[]]
            for item in v:
                if str(item).strip() == "":
                    paragraphs.append([])
                else:
                    paragraphs[-1].append(str(item))
            return "\n\n".join(
                " ".join(sentences)
                for sentences in paragraphs
                if sentences
            )
        return v


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
    image_url: str | None = None  # optional cover image

    @field_validator("body_md", mode="before")
    @classmethod
    def coerce_list_to_str(cls, v: Union[str, list]) -> str:
        """Accept either a plain string or a list of strings.

        Empty string "" = paragraph break.
        Non-empty strings next to each other = same paragraph (joined with space).
        """
        if isinstance(v, list):
            paragraphs: list[list[str]] = [[]]
            for item in v:
                if str(item).strip() == "":
                    paragraphs.append([])
                else:
                    paragraphs[-1].append(str(item))
            return "\n\n".join(
                " ".join(sentences)
                for sentences in paragraphs
                if sentences
            )
        return v
