"""Content service: category tree, topics, blog posts, Markdown rendering (Requirement 3).

Depends only on the :class:`~app.storage.base.StorageBackend` interface.

S3 key layout (see design.md)::

    categories/{id}.json        Category
    categories/_index.json      {"ids": ["id1", "id2", ...]}   ordered id list
    blog/{id}.json              BlogPost
    blog/_index.json            {"posts": {"<id>": {"slug", "title", "status", "published_at"}}}

The ``_index`` objects are an optimisation hint listing which objects exist; the individual
object files are the source of truth (e.g. post ``status`` is always read from the post
file, never from the index). If an index object is missing, the service falls back to
listing the prefix, so authors who forget to update an index still see their content.

Drafts are never returned from the public API unless ``include_drafts=True`` is passed
explicitly (R3.5).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timezone

import markdown as _markdown
from pydantic import BaseModel, ValidationError

from app.models.content import BlogPost, Category
from app.storage.base import NotFound, StorageBackend

logger = logging.getLogger(__name__)

CATEGORIES_PREFIX = "categories/"
CATEGORIES_INDEX_KEY = "categories/_index.json"
BLOG_PREFIX = "blog/"
BLOG_INDEX_KEY = "blog/_index.json"

_MARKDOWN_EXTENSIONS = ["extra", "sane_lists"]


@dataclass
class CategoryNode:
    """A category together with its (ordered) subcategories."""

    category: Category
    children: list["CategoryNode"] = field(default_factory=list)


@dataclass
class CategoryView:
    """Everything needed to render one category page (R3.2)."""

    category: Category
    breadcrumbs: list[Category]  # root ... parent (excludes the category itself)
    subcategories: list[Category]
    topics: list[BlogPost]  # published only unless include_drafts=True


def render_markdown(text: str) -> str:
    """Render Markdown to HTML (R3.3).

    Content is authored by the trusted team via GitHub/S3, so raw HTML in Markdown is
    passed through. Do not feed user-submitted text through this function.
    """
    return _markdown.markdown(text or "", extensions=_MARKDOWN_EXTENSIONS)


class RenderedPost(BaseModel):
    post: BlogPost
    body_html: str


def _sort_timestamp(post: BlogPost) -> float:
    """Sort key for reverse-chronological order; undated posts sort last."""
    if post.published_at is None:
        return float("-inf")
    moment = post.published_at
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()


def _sorted_newest_first(posts: list[BlogPost]) -> list[BlogPost]:
    return sorted(posts, key=lambda p: (-_sort_timestamp(p), p.title))


class ContentService:
    def __init__(self, storage: StorageBackend) -> None:
        self._storage = storage

    # ------------------------------------------------------------------ loading

    async def _ids_for(self, prefix: str, index_key: str, index_field: str) -> list[str]:
        """Object ids for ``prefix`` from the index, or by listing if no index exists."""
        try:
            index = await self._storage.get_json(index_key)
        except NotFound:
            ids: list[str] = []
            for key in await self._storage.list(prefix):
                name = key[len(prefix) :]
                if name.endswith(".json") and "/" not in name and not name.startswith("_"):
                    ids.append(name[: -len(".json")])
            return ids
        entries = index.get(index_field, [])
        if isinstance(entries, dict):  # blog index maps id -> summary
            return list(entries.keys())
        return [str(i) for i in entries]

    async def _load_model(self, key: str, model: type[BaseModel]):
        """Load and validate one object; ``None`` if missing or malformed.

        A single bad file must not take down a whole listing page.
        """
        try:
            data = await self._storage.get_json(key)
        except NotFound:
            return None
        try:
            return model.model_validate(data)
        except ValidationError:
            logger.warning("Skipping invalid content object %s", key, exc_info=True)
            return None

    async def _all_categories(self) -> list[Category]:
        ids = await self._ids_for(CATEGORIES_PREFIX, CATEGORIES_INDEX_KEY, "ids")
        loaded = [await self._load_model(f"{CATEGORIES_PREFIX}{i}.json", Category) for i in ids]
        return [c for c in loaded if c is not None]

    async def _all_posts(self, include_drafts: bool = False) -> list[BlogPost]:
        ids = await self._ids_for(BLOG_PREFIX, BLOG_INDEX_KEY, "posts")
        loaded = [await self._load_model(f"{BLOG_PREFIX}{i}.json", BlogPost) for i in ids]
        # Status comes from the post file itself (authoritative), not from the index.
        return [p for p in loaded if p is not None and (include_drafts or p.status == "published")]

    # ---------------------------------------------------------------- categories

    async def get_category_tree(self) -> list[CategoryNode]:
        """Assemble the multi-level tree (R3.1); returns the root nodes.

        Siblings are ordered by ``(order, title)``. Categories whose parent does not exist
        (or that sit in a parent cycle) are unreachable from a root and are omitted.
        """
        categories = await self._all_categories()
        nodes = {c.id: CategoryNode(c) for c in categories}
        roots: list[CategoryNode] = []
        for node in nodes.values():
            parent_id = node.category.parent_id
            if parent_id is None:
                roots.append(node)
            elif parent_id in nodes and parent_id != node.category.id:
                nodes[parent_id].children.append(node)

        def order(items: list[CategoryNode]) -> None:
            items.sort(key=lambda n: (n.category.order, n.category.title))
            for item in items:
                order(item.children)

        order(roots)
        return roots

    async def get_category(self, category_id: str) -> Category | None:
        """One category by id, or ``None`` if it does not exist."""
        return await self._load_model(f"{CATEGORIES_PREFIX}{category_id}.json", Category)

    async def get_category_view(
        self, slug: str, *, include_drafts: bool = False
    ) -> CategoryView:
        """Category page data: subcategories and topics. Raises NotFound for unknown slug."""
        categories = await self._all_categories()
        by_id = {c.id: c for c in categories}
        category = next((c for c in categories if c.slug == slug), None)
        if category is None:
            raise NotFound(f"{CATEGORIES_PREFIX}{slug}")

        breadcrumbs: list[Category] = []
        seen = {category.id}
        parent = by_id.get(category.parent_id) if category.parent_id else None
        while parent is not None and parent.id not in seen:
            breadcrumbs.insert(0, parent)
            seen.add(parent.id)
            parent = by_id.get(parent.parent_id) if parent.parent_id else None

        subcategories = sorted(
            (c for c in categories if c.parent_id == category.id),
            key=lambda c: (c.order, c.title),
        )
        topics = await self.list_topics(category.id, include_drafts=include_drafts)
        return CategoryView(category, breadcrumbs, subcategories, topics)

    async def list_topics(
        self, category_id: str, *, include_drafts: bool = False
    ) -> list[BlogPost]:
        """Topics (posts) in a category, newest first. Drafts excluded by default (R3.5)."""
        posts = await self._all_posts(include_drafts)
        return _sorted_newest_first([p for p in posts if p.category_id == category_id])

    # --------------------------------------------------------------------- blog

    async def list_posts(
        self, *, limit: int | None = None, include_drafts: bool = False
    ) -> list[BlogPost]:
        """All posts, reverse-chronological (R3.4). Drafts excluded by default (R3.5)."""
        posts = _sorted_newest_first(await self._all_posts(include_drafts))
        return posts if limit is None else posts[:limit]

    async def get_post(self, slug: str, *, include_drafts: bool = False) -> BlogPost:
        """Load a post by slug. Raises NotFound if missing, or a draft on public access."""
        for post in await self._all_posts(include_drafts):
            if post.slug == slug:
                return post
        raise NotFound(f"{BLOG_PREFIX}{slug}")

    async def get_rendered_post(
        self, slug: str, *, include_drafts: bool = False
    ) -> RenderedPost:
        """Load a post and render its Markdown body to HTML (R3.3)."""
        post = await self.get_post(slug, include_drafts=include_drafts)
        return RenderedPost(post=post, body_html=render_markdown(post.body_md))
