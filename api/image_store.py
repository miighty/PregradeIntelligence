from __future__ import annotations

"""Very small, local image store for API responses.

In Lambda, you would replace this with S3 presigned URLs, etc.
For local/dev we write to ./exports/.

This keeps the API deterministic enough for testing while giving callers
something to fetch.
"""

import os
from typing import Tuple

from PIL import Image


def save_png(img: Image.Image, request_id: str, name: str) -> str:
    out_dir = os.path.join(os.getcwd(), "exports", "grade")
    os.makedirs(out_dir, exist_ok=True)
    safe = "".join(ch for ch in name if ch.isalnum() or ch in {"_", "-"}).strip() or "img"
    path = os.path.join(out_dir, f"{request_id}__{safe}.png")
    img.save(path)
    return path
