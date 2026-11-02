"""One-off script to fix the Mleko category image URL in S3."""
import asyncio
from app.storage.factory import get_storage_backend


async def fix():
    s = get_storage_backend()
    await s.put_json("categories/cat-biedronka-nabial-mleko.json", {
        "id": "cat-biedronka-nabial-mleko",
        "slug": "biedronka-nabial-mleko",
        "title": "Mleko",
        "parent_id": "cat-biedronka-nabial",
        "order": 1,
        "description_md": "Analiza mleka dostępnego w Biedronce.",
        "image_url": "images/category/Biedronka/Nabial/mlekopiatnicatitle.jpg",
    })
    print("Done — Mleko image URL updated in S3.")


asyncio.run(fix())
