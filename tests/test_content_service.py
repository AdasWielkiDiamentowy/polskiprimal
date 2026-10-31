"""ContentService + model tests against the in-memory fake backend."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import AvailabilitySlot, Reservation, ThemeConfig, User
from app.services.content_service import ContentService, render_markdown
from app.storage import InMemoryStorageBackend
from app.storage.base import NotFound


def _cat(id_, title, parent_id=None, order=0, slug=None):
    return {
        "id": id_,
        "slug": slug or id_,
        "title": title,
        "parent_id": parent_id,
        "order": order,
        "description_md": "",
    }


def _post(id_, category_id=None, status="published", published_at="2025-01-01T10:00:00Z", **kw):
    return {
        "id": id_,
        "slug": kw.get("slug", id_),
        "title": kw.get("title", id_.upper()),
        "category_id": category_id,
        "body_md": kw.get("body_md", "text"),
        "author": "Ala",
        "status": status,
        "published_at": published_at,
    }


@pytest.fixture
def backend() -> InMemoryStorageBackend:
    return InMemoryStorageBackend()


@pytest.fixture
def service(backend) -> ContentService:
    return ContentService(backend)


async def _seed(backend, categories, posts, *, with_index=True):
    for c in categories:
        await backend.put_json(f"categories/{c['id']}.json", c)
    for p in posts:
        await backend.put_json(f"blog/{p['id']}.json", p)
    if with_index:
        await backend.put_json("categories/_index.json", {"ids": [c["id"] for c in categories]})
        await backend.put_json(
            "blog/_index.json",
            {"posts": {p["id"]: {"slug": p["slug"], "title": p["title"]} for p in posts}},
        )


# --------------------------------------------------------------- category tree


@pytest.mark.anyio
async def test_tree_assembles_three_levels_in_order(backend, service):
    await _seed(
        backend,
        [
            _cat("keto", "Keto", order=2),
            _cat("primal", "Primal", order=1),
            _cat("restauracje", "Restauracje", parent_id="keto", order=1),
            _cat("warszawa", "Warszawa", parent_id="restauracje"),
        ],
        [],
    )
    tree = await service.get_category_tree()

    assert [n.category.id for n in tree] == ["primal", "keto"]
    keto = tree[1]
    assert [c.category.id for c in keto.children] == ["restauracje"]
    assert [c.category.id for c in keto.children[0].children] == ["warszawa"]
    assert tree[0].children == []


@pytest.mark.anyio
async def test_tree_omits_orphans_and_cycles(backend, service):
    await _seed(
        backend,
        [
            _cat("root", "Root"),
            _cat("orphan", "Orphan", parent_id="missing"),
            _cat("a", "A", parent_id="b"),
            _cat("b", "B", parent_id="a"),
        ],
        [],
    )
    tree = await service.get_category_tree()
    assert [n.category.id for n in tree] == ["root"]


@pytest.mark.anyio
async def test_tree_without_index_falls_back_to_listing_and_empty_store(backend, service):
    assert await service.get_category_tree() == []

    await _seed(backend, [_cat("a", "A")], [], with_index=False)
    assert [n.category.id for n in await service.get_category_tree()] == ["a"]


@pytest.mark.anyio
async def test_tree_skips_invalid_category_file(backend, service):
    await _seed(backend, [_cat("good", "Good")], [])
    await backend.put_json("categories/bad.json", {"id": "bad"})  # missing fields
    await backend.put_json("categories/_index.json", {"ids": ["good", "bad", "ghost"]})
    assert [n.category.id for n in await service.get_category_tree()] == ["good"]


# ---------------------------------------------------------------- category view


@pytest.mark.anyio
async def test_category_view_lists_subcategories_and_published_topics_only(backend, service):
    await _seed(
        backend,
        [_cat("keto", "Keto"), _cat("lista", "Lista", parent_id="keto")],
        [
            _post("p1", "keto", published_at="2025-01-01T00:00:00Z"),
            _post("p2", "keto", published_at="2025-03-01T00:00:00Z"),
            _post("secret", "keto", status="draft"),
            _post("other", "lista"),
        ],
    )
    view = await service.get_category_view("keto")

    assert [c.id for c in view.subcategories] == ["lista"]
    assert [p.id for p in view.topics] == ["p2", "p1"]  # newest first, no draft
    assert view.breadcrumbs == []

    child = await service.get_category_view("lista")
    assert [c.id for c in child.breadcrumbs] == ["keto"]


@pytest.mark.anyio
async def test_category_view_unknown_slug_raises_not_found(service):
    with pytest.raises(NotFound):
        await service.get_category_view("nope")


# ------------------------------------------------------------------ draft filter


@pytest.mark.anyio
async def test_drafts_hidden_from_every_public_view(backend, service):
    await _seed(backend, [_cat("c", "C")], [_post("pub", "c"), _post("draft", "c", status="draft")])

    assert [p.id for p in await service.list_posts()] == ["pub"]
    assert [p.id for p in await service.list_topics("c")] == ["pub"]
    with pytest.raises(NotFound):
        await service.get_post("draft")
    with pytest.raises(NotFound):
        await service.get_rendered_post("draft")


@pytest.mark.anyio
async def test_draft_status_comes_from_post_file_not_stale_index(backend, service):
    await _seed(backend, [], [_post("x", status="draft")])
    # Index claims published; the post file (source of truth) says draft.
    await backend.put_json(
        "blog/_index.json", {"posts": {"x": {"slug": "x", "title": "X", "status": "published"}}}
    )
    assert await service.list_posts() == []


@pytest.mark.anyio
async def test_drafts_visible_only_when_explicitly_requested(backend, service):
    await _seed(backend, [], [_post("pub"), _post("draft", status="draft", published_at=None)])
    posts = await service.list_posts(include_drafts=True)
    assert {p.id for p in posts} == {"pub", "draft"}
    assert (await service.get_post("draft", include_drafts=True)).status == "draft"


# ------------------------------------------------------------------ blog + render


@pytest.mark.anyio
async def test_list_posts_reverse_chronological_with_limit_and_undated_last(backend, service):
    await _seed(
        backend,
        [],
        [
            _post("old", published_at="2024-01-01T00:00:00Z"),
            _post("undated", published_at=None),
            _post("new", published_at="2025-06-01T00:00:00Z"),
            _post("naive", published_at="2025-01-01T00:00:00"),
        ],
    )
    assert [p.id for p in await service.list_posts()] == ["new", "naive", "old", "undated"]
    assert [p.id for p in await service.list_posts(limit=2)] == ["new", "naive"]


@pytest.mark.anyio
async def test_get_rendered_post_converts_markdown(backend, service):
    await _seed(backend, [], [_post("a", slug="moj-wpis", body_md="# Cześć\n\n- **jeden**\n- dwa")])
    rendered = await service.get_rendered_post("moj-wpis")

    assert rendered.post.id == "a"
    assert "<h1>Cześć</h1>" in rendered.body_html
    assert "<strong>jeden</strong>" in rendered.body_html
    assert "<li>dwa</li>" in rendered.body_html


@pytest.mark.anyio
async def test_get_post_unknown_slug_raises_not_found(service):
    with pytest.raises(NotFound):
        await service.get_post("nope")


def test_render_markdown_handles_empty():
    assert render_markdown("") == ""


# ------------------------------------------------------------------------ models


def test_user_role_and_email_validated():
    base = dict(
        id="u1", email="a@b.pl", password_hash="x", display_name="A",
        created_at="2025-01-01T00:00:00Z",
    )
    assert User(role="supplier", **base).verified_farmer is False
    with pytest.raises(ValidationError):
        User(role="superuser", **base)
    with pytest.raises(ValidationError):
        User(role="admin", **{**base, "email": "not-an-email"})


def test_post_defaults_to_draft_and_models_round_trip():
    from app.models import BlogPost

    post = BlogPost(id="1", slug="s", title="T", body_md="b", author="A")
    assert post.status == "draft"

    slot = AvailabilitySlot(
        id="s1", supplier_id="u1", product="Truskawki", quantity=5, unit="kg",
        market_location="Piaseczno", date="2025-06-07", time_start="07:00", time_end="12:00",
    )
    assert AvailabilitySlot.model_validate_json(slot.model_dump_json()) == slot

    res = Reservation(
        id="r1", slot_id="s1", consumer_ref="jan", quantity=2, created_at="2025-06-01T10:00:00Z"
    )
    assert res.status == "requested"
    assert ThemeConfig().primary_color == "#2e7d32"
