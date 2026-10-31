"""Shared pytest configuration."""

import pytest


@pytest.fixture
def anyio_backend() -> str:
    """Run async tests (``@pytest.mark.anyio``) on asyncio only."""
    return "asyncio"
