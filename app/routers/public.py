"""Public-facing routes: homepage, categories, blog, calendar placeholder, health check.

All content is read through the StorageBackend via the services (Requirements 1.2, 2.2).
A missing category or post raises ``NotFound``, which the app-level handler renders as the
404 page (R3.7); drafts are never visible here (R3.5).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.deps import get_storage
from app.services.content_service import ContentService
from app.storage.base import StorageBackend, StorageError
from app.templating import render_page

logger = logging.getLogger(__name__)

router = APIRouter()

HOME_RECENT_POSTS = 6


def content_service(request: Request) -> ContentService:
    return ContentService(get_storage(request))


@router.get("/health", include_in_schema=True)
async def health() -> JSONResponse:
    """Health-check endpoint for uptime monitoring (Requirement 10.6)."""
    return JSONResponse({"status": "ok"})


@router.get("/", response_class=HTMLResponse)
async def homepage(request: Request) -> HTMLResponse:
    """Homepage: recent posts and top-level categories.

    If storage is not configured yet the homepage still renders (with empty sections), so
    a freshly deployed site is reachable before content storage is set up (R1.1, R1.5).
    """
    posts, categories = [], []
    try:
        service = content_service(request)
        posts = await service.list_posts(limit=HOME_RECENT_POSTS)
        categories = await service.get_category_tree()
    except StorageError:
        logger.warning("Homepage rendered without content: storage unavailable", exc_info=True)
    return await render_page(
        request,
        "index.html",
        {
            "title": "Zdrowe jedzenie prosto od rolnika",
            "posts": posts,
            "categories": categories,
        },
    )


@router.get("/kategorie", response_class=HTMLResponse)
async def category_index(
    request: Request, service: ContentService = Depends(content_service)
) -> HTMLResponse:
    tree = await service.get_category_tree()
    return await render_page(
        request, "categories.html", {"title": "Kategorie", "categories": tree}
    )


@router.get("/kategorie/{slug}", response_class=HTMLResponse)
async def category_detail(
    slug: str, request: Request, service: ContentService = Depends(content_service)
) -> HTMLResponse:
    view = await service.get_category_view(slug)  # NotFound -> 404 page
    return await render_page(
        request, "category.html", {"title": view.category.title, "view": view}
    )


@router.get("/blog", response_class=HTMLResponse)
async def blog_list(
    request: Request, service: ContentService = Depends(content_service)
) -> HTMLResponse:
    posts = await service.list_posts()  # newest first, drafts excluded
    return await render_page(request, "blog_list.html", {"title": "Blog", "posts": posts})


@router.get("/blog/{slug}", response_class=HTMLResponse)
async def blog_detail(
    slug: str, request: Request, service: ContentService = Depends(content_service)
) -> HTMLResponse:
    rendered = await service.get_rendered_post(slug)  # NotFound (incl. drafts) -> 404 page
    post = rendered.post
    category = await service.get_category(post.category_id) if post.category_id else None
    return await render_page(
        request,
        "blog_detail.html",
        {
            "title": post.title,
            "post": post,
            "body_html": rendered.body_html,
            "category": category,
        },
    )


@router.get("/kalendarz", response_class=HTMLResponse)
async def calendar_placeholder(request: Request) -> HTMLResponse:
    """Calendar is built in a later task; show the "coming soon" notice (R1.3)."""
    return await render_page(
        request,
        "coming_soon.html",
        {
            "title": "Kalendarz rolników",
            "feature_title": "Kalendarz rolników",
            "feature_text": (
                "Wkrótce sprawdzisz tu, kiedy i gdzie lokalni rolnicy będą na targu, "
                "i wyślesz prośbę o rezerwację produktów."
            ),
        },
    )
