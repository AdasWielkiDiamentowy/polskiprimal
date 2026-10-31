"""Integration tests for the public content pages, theming, 404 and coming-soon.

Covers Requirements 1.2, 1.3, 3.2, 3.3, 3.4, 3.5, 3.7, 9.1-9.4 using the in-memory
backend seeded from the repository's ``content/`` directory.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.seed import seed_storage
from app.storage import InMemoryStorageBackend, StorageError
from app.storage.base import StorageBackend


@pytest.fixture
def storage() -> InMemoryStorageBackend:
    backend = InMemoryStorageBackend()
    written = asyncio.run(seed_storage(backend))
    assert "config/theme.json" in written
    return backend


@pytest.fixture
def client(storage) -> TestClient:
    with TestClient(create_app(storage=storage)) as c:
        yield c


# ------------------------------------------------------------------ homepage


def test_homepage_shows_recent_posts_newest_first_without_drafts(client):
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert "Pierwsze dni bez cukru" in html
    assert "Witaj na polskiprimal.pl" in html
    assert "Szkic: analiza nawozów" not in html  # draft (R3.5)
    assert html.index("Pierwsze dni bez cukru") < html.index("Witaj na polskiprimal.pl")  # R3.4
    assert "Składniki produktów" in html  # category tree
    assert 'data-coming-soon' in html  # R1.3


def test_homepage_still_renders_when_storage_is_unconfigured(monkeypatch):
    """No storage configured -> empty sections instead of an error (R1.1, R1.5)."""
    for var in ("S3_BUCKET", "AWS_REGION"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    from app.config import get_settings
    from app.storage.factory import get_storage_backend

    get_settings.cache_clear()
    get_storage_backend.cache_clear()
    try:
        with TestClient(create_app()) as c:
            resp = c.get("/")
    finally:
        get_settings.cache_clear()
        get_storage_backend.cache_clear()
    assert resp.status_code == 200
    assert "Pierwsze wpisy pojawią się już wkrótce" in resp.text


# ------------------------------------------------------------------ categories


def test_category_index_lists_nested_tree(client):
    resp = client.get("/kategorie")
    assert resp.status_code == 200
    assert "/kategorie/skladniki-produktow" in resp.text
    assert "/kategorie/biedronka" in resp.text


def test_category_view_lists_subcategories_and_published_topics(client):
    resp = client.get("/kategorie/skladniki-produktow")
    assert resp.status_code == 200
    html = resp.text
    assert "Podkategorie" in html and "/kategorie/biedronka" in html  # R3.2
    assert "Jak czytać skład produktu" in html
    assert "Szkic: analiza nawozów" not in html
    assert "<strong>Biedronki</strong>" in html  # description rendered as Markdown


def test_subcategory_shows_breadcrumb_to_parent(client):
    resp = client.get("/kategorie/biedronka")
    assert resp.status_code == 200
    assert 'href="/kategorie/skladniki-produktow"' in resp.text


def test_unknown_category_returns_404_page(client):
    resp = client.get("/kategorie/nie-ma-takiej")
    assert resp.status_code == 404
    assert "Nie znaleziono strony" in resp.text  # R3.7


# ------------------------------------------------------------------ blog


def test_blog_list_is_reverse_chronological_and_excludes_drafts(client):
    resp = client.get("/blog")
    assert resp.status_code == 200
    html = resp.text
    order = [
        "Pierwsze dni bez cukru",
        "Czym jest indeks glikemiczny",
        "Zakupy na tydzień",
        "Jak czytać skład produktu",
        "Witaj na polskiprimal.pl",
    ]
    positions = [html.index(t) for t in order]
    assert positions == sorted(positions)
    assert "Szkic: analiza nawozów" not in html


def test_blog_detail_renders_markdown_and_category_link(client):
    resp = client.get("/blog/jak-czytac-sklad-produktu")
    assert resp.status_code == 200
    html = resp.text
    assert "<h2>Kolejność ma znaczenie</h2>" in html  # R3.3
    assert "<strong>od najwięcej do najmniej</strong>" in html
    assert 'href="/kategorie/skladniki-produktow"' in html
    assert "5 czerwca 2025" in html


def test_draft_post_is_404(client):
    resp = client.get("/blog/szkic-analiza-nawozow")
    assert resp.status_code == 404
    assert "Nie znaleziono strony" in resp.text


def test_unknown_post_is_404_not_500(client):
    resp = client.get("/blog/nie-istnieje")
    assert resp.status_code == 404


def test_unknown_route_renders_404_page(client):
    resp = client.get("/to-nie-istnieje")
    assert resp.status_code == 404
    assert "Nie znaleziono strony" in resp.text


def test_health_endpoint_is_unaffected_by_error_handlers(client):
    assert client.get("/health").json() == {"status": "ok"}


# ------------------------------------------------------------------ coming soon


def test_calendar_shows_coming_soon_notice(client):
    resp = client.get("/kalendarz")
    assert resp.status_code == 200
    assert "Wkrótce" in resp.text and "Kalendarz rolników" in resp.text  # R1.3


# ------------------------------------------------------------------ theming


def test_theme_variables_injected_from_storage(client):
    html = client.get("/").text
    assert "--primary-color: #2e7d32;" in html  # R9.1, R9.2
    assert "--accent-color: #ff8f00;" in html
    assert "--font-family: Inter, system-ui, sans-serif;" in html


def test_theme_change_applies_on_next_render_without_restart(client, storage):
    asyncio.run(
        storage.put_json(
            "config/theme.json",
            {"primary_color": "#112233", "accent_color": "tomato", "font_family": "Georgia, serif"},
        )
    )
    html = client.get("/blog").text  # R9.3
    assert "--primary-color: #112233;" in html
    assert "--accent-color: tomato;" in html
    assert "--font-family: Georgia, serif;" in html


def test_invalid_theme_values_fall_back_to_defaults(client, storage):
    asyncio.run(
        storage.put_json(
            "config/theme.json",
            {
                "primary_color": "red; } body { display:none",
                "accent_color": "#abc",
                "font_family": "x</style><script>alert(1)</script>",
            },
        )
    )
    html = client.get("/").text
    assert "display:none" not in html
    assert "<script>alert(1)" not in html
    assert "--primary-color: #2e7d32;" in html  # default
    assert "--accent-color: #abc;" in html  # valid value kept


def test_missing_theme_file_uses_defaults(storage):
    asyncio.run(storage.delete("config/theme.json"))
    with TestClient(create_app(storage=storage)) as c:
        resp = c.get("/")
    assert resp.status_code == 200
    assert "--primary-color: #2e7d32;" in resp.text


def test_layout_is_responsive_and_maps_tailwind_tokens(client):
    html = client.get("/").text
    assert 'name="viewport" content="width=device-width, initial-scale=1.0"' in html  # R9.4
    assert "var(--primary-color)" in html  # Tailwind token mapping
    assert "md:hidden" in html  # mobile menu


# ------------------------------------------------------------------ storage failures


class _BrokenStorage(InMemoryStorageBackend):
    async def get_json(self, key: str) -> dict:
        raise StorageError("boom")

    async def list(self, prefix: str) -> list[str]:
        raise StorageError("boom")


def test_storage_outage_gives_503_page_not_a_stack_trace():
    broken: StorageBackend = _BrokenStorage()
    with TestClient(create_app(storage=broken)) as c:
        blog = c.get("/blog")
        home = c.get("/")
    assert blog.status_code == 503
    assert "Treść chwilowo niedostępna" in blog.text
    assert home.status_code == 200  # homepage degrades gracefully


# ------------------------------------------------------------------ seeding


def test_seed_does_not_overwrite_existing_objects_by_default(storage):
    asyncio.run(storage.put_json("config/theme.json", {"primary_color": "#000000"}))
    written = asyncio.run(seed_storage(storage))
    assert "config/theme.json" not in written
    assert asyncio.run(storage.get_json("config/theme.json"))["primary_color"] == "#000000"

    written = asyncio.run(seed_storage(storage, overwrite=True))
    assert "config/theme.json" in written
