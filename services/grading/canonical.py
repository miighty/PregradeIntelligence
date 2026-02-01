from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import Any, Optional

from PIL import Image

from services.card_warp import warp_card_best_effort


CANONICAL_W = 744
CANONICAL_H = 1040


@dataclass(frozen=True)
class CanonicalImage:
    image: Image.Image
    warp_used: bool
    warp_reason: str
    warp_debug: dict[str, Any]


def load_image_from_bytes(image_bytes: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(image_bytes))
    img.load()
    return img.convert("RGB")


def load_image_from_base64(data: str) -> bytes:
    return base64.b64decode(data)


def canonicalize(img: Image.Image) -> CanonicalImage:
    """Return a canonical, grading-ready image.

    Steps:
      - convert to RGB
      - best-effort warp to CANONICAL_W x CANONICAL_H

    Note: orientation normalization (upright) can be added once we have reliable
    orientation detection. For now we assume warp output is roughly upright for
    most user photos; overlay outputs will reveal failures.
    """

    rgb = img.convert("RGB")

    warped, warp_used, warp_reason, warp_debug = warp_card_best_effort(
        rgb,
    )

    # Ensure canonical size if warp succeeded; otherwise, resize to keep downstream stable.
    if warped.size != (CANONICAL_W, CANONICAL_H):
        warped = warped.resize((CANONICAL_W, CANONICAL_H))

    return CanonicalImage(
        image=warped,
        warp_used=warp_used,
        warp_reason=warp_reason,
        warp_debug=warp_debug,
    )
