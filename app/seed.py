"""Load the sample/starter content from ``content/`` into the configured StorageBackend.

The ``content/`` directory mirrors the storage key layout from design.md
(``categories/…``, ``blog/…``, ``config/theme.json``), so the team can edit the same JSON
and Markdown in GitHub and publish it with::

    python -m app.seed              # upload only objects that do not exist yet
    python -m app.seed --overwrite  # replace existing objects with the repo versions

By default existing objects are left untouched, so running the seed against a live bucket
never clobbers content that was edited there. With ``STORAGE_BACKEND=memory`` the app seeds
itself on startup, so a fresh local checkout renders real pages with no AWS account.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

from app.storage.base import NotFound, StorageBackend

logger = logging.getLogger(__name__)

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"


async def seed_storage(
    storage: StorageBackend,
    content_dir: Path = CONTENT_DIR,
    *,
    overwrite: bool = False,
) -> list[str]:
    """Upload every ``*.json`` under ``content_dir``; return the keys written."""
    written: list[str] = []
    if not content_dir.is_dir():
        logger.warning("Seed directory %s not found; nothing to load", content_dir)
        return written

    for path in sorted(content_dir.rglob("*.json")):
        key = path.relative_to(content_dir).as_posix()
        if not overwrite:
            try:
                await storage.get_json(key)
                continue  # already present; keep it
            except NotFound:
                pass
        await storage.put_json(key, json.loads(path.read_text(encoding="utf-8")))
        written.append(key)
    return written


def main() -> None:
    from app.storage.factory import get_storage_backend

    parser = argparse.ArgumentParser(description="Load starter content into storage.")
    parser.add_argument("--overwrite", action="store_true", help="replace existing objects")
    args = parser.parse_args()

    written = asyncio.run(seed_storage(get_storage_backend(), overwrite=args.overwrite))
    print(f"Wrote {len(written)} object(s).")
    for key in written:
        print(f"  {key}")


if __name__ == "__main__":
    main()
