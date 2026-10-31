"""Tests for the health check and homepage (Requirements 1.1, 10.6)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_health_returns_200():
    """/health returns 200 with an ok status (R10.6)."""
    with _client() as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_homepage_renders():
    """Homepage renders static placeholder content without a database (R1.1)."""
    with _client() as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    # Polish placeholder content is present.
    assert "polskiprimal.pl" in resp.text
