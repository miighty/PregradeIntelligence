"""Card number extraction (x/yy) from Pokémon card images.

Tesseract often fails on the tiny bottom-corner number/total text.
This module uses a deterministic, lightweight template matcher:
- Crop region
- Upscale + binarize for dark text
- Segment glyphs by connected components
- Classify glyphs by matching against rendered templates for multiple fonts

Goal: be reliable on real-world scans with minimal dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


@dataclass(frozen=True)
class ParsedNumber:
    number: str  # e.g. "6/95"
    confidence: float


# Common font paths on macOS/Linux. We'll try these and fall back to PIL default.
_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Helvetica.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def parse_card_number_from_crop(crop: Image.Image) -> Optional[ParsedNumber]:
    """Parse x/yy from an already-cropped number region."""
    # Normalize input
    img = crop.convert("L")

    # Increase contrast by stretching
    img = ImageOps.autocontrast(img)

    # Upscale aggressively
    w, h = img.size
    scale = 10
    img = img.resize((max(1, w * scale), max(1, h * scale)), resample=Image.Resampling.BICUBIC)

    # Binarize for dark text on lighter background.
    arr = np.array(img, dtype=np.uint8)

    # Adaptive-ish threshold: use a percentile of brightness.
    # Digits are usually among the darkest pixels.
    t = int(np.percentile(arr, 35))
    bw = (arr <= t).astype(np.uint8)  # 1 for ink

    # Remove tiny specks
    bw = _remove_small_components(bw, min_area=120)

    boxes = _connected_component_boxes(bw)
    if not boxes:
        return None

    # Filter to likely text line (exclude very tall/very short)
    boxes = [b for b in boxes if 20 <= b.h <= 220]
    if not boxes:
        return None

    boxes.sort(key=lambda b: b.x)

    glyphs: list[np.ndarray] = []
    for b in boxes:
        g = bw[b.y : b.y + b.h, b.x : b.x + b.w]
        # Skip extremely narrow noise
        if g.shape[1] < 10:
            continue
        glyphs.append(_render_glyph(g))

    if not glyphs:
        return None

    templates = _build_templates()

    chars: list[str] = []
    scores: list[float] = []
    for g in glyphs:
        ch, score = _match_template(g, templates)
        if ch is None:
            continue
        chars.append(ch)
        scores.append(score)

    if not chars:
        return None

    text = "".join(chars)

    # Normalise common confusions
    text = text.replace("I", "1").replace("l", "1")

    # Heuristic: we expect something like 1-3 digits / 1-3 digits
    parsed = _extract_number_pattern(text)
    if not parsed:
        return None

    conf = float(np.clip(np.mean(scores) if scores else 0.0, 0.0, 1.0))
    return ParsedNumber(number=parsed, confidence=round(conf, 2))


# -----------------
# Internals


@dataclass(frozen=True)
class _Box:
    x: int
    y: int
    w: int
    h: int


def _extract_number_pattern(s: str) -> Optional[str]:
    # Keep only digits and '/'
    s2 = "".join(ch for ch in s if ch.isdigit() or ch == "/")
    if "/" not in s2:
        return None
    left, right = s2.split("/", 1)
    left = "".join(ch for ch in left if ch.isdigit())
    right = "".join(ch for ch in right if ch.isdigit())
    if not (1 <= len(left) <= 3 and 1 <= len(right) <= 3):
        return None
    return f"{int(left)}/{int(right)}"


def _render_glyph(g: np.ndarray) -> np.ndarray:
    """Center glyph into a fixed-size canvas."""
    # Pad
    h, w = g.shape
    pad = 12
    canvas = np.zeros((h + pad * 2, w + pad * 2), dtype=np.uint8)
    canvas[pad : pad + h, pad : pad + w] = g

    # Resize to fixed size
    img = Image.fromarray((canvas * 255).astype(np.uint8), mode="L")
    img = img.resize((40, 56), resample=Image.Resampling.NEAREST)
    out = (np.array(img, dtype=np.uint8) > 0).astype(np.uint8)
    return out


def _match_template(g: np.ndarray, templates: dict[str, list[np.ndarray]]) -> tuple[Optional[str], float]:
    best_ch: Optional[str] = None
    best_score = -1e9

    for ch, variants in templates.items():
        for t in variants:
            # similarity = 1 - normalized Hamming distance
            dist = np.mean(g != t)
            score = 1.0 - dist
            if score > best_score:
                best_score = score
                best_ch = ch

    # Reject if too low.
    if best_score < 0.72:
        return None, 0.0

    return best_ch, float(best_score)


def _build_templates() -> dict[str, list[np.ndarray]]:
    chars = list("0123456789/")

    fonts: list[ImageFont.FreeTypeFont | ImageFont.ImageFont] = []
    for p in _FONT_CANDIDATES:
        try:
            fonts.append(ImageFont.truetype(p, 48))
        except Exception:
            pass
    if not fonts:
        fonts.append(ImageFont.load_default())

    templates: dict[str, list[np.ndarray]] = {c: [] for c in chars}
    for font in fonts:
        for c in chars:
            img = Image.new("L", (60, 80), 0)
            d = ImageDraw.Draw(img)
            d.text((5, 0), c, fill=255, font=font)
            img = ImageOps.autocontrast(img)
            img = img.resize((40, 56), resample=Image.Resampling.BICUBIC)
            arr = (np.array(img, dtype=np.uint8) > 64).astype(np.uint8)
            templates[c].append(arr)

    return templates


def _connected_component_boxes(bw: np.ndarray) -> list[_Box]:
    """Return bounding boxes for connected components in bw (1=ink)."""
    h, w = bw.shape
    visited = np.zeros_like(bw, dtype=np.uint8)
    boxes: list[_Box] = []

    # 4-neighbourhood
    for y in range(h):
        for x in range(w):
            if bw[y, x] == 0 or visited[y, x] == 1:
                continue
            # BFS
            q = [(x, y)]
            visited[y, x] = 1
            minx = maxx = x
            miny = maxy = y
            area = 0

            while q:
                cx, cy = q.pop()
                area += 1
                if cx < minx:
                    minx = cx
                if cx > maxx:
                    maxx = cx
                if cy < miny:
                    miny = cy
                if cy > maxy:
                    maxy = cy

                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < w and 0 <= ny < h:
                        if bw[ny, nx] == 1 and visited[ny, nx] == 0:
                            visited[ny, nx] = 1
                            q.append((nx, ny))

            bx = _Box(x=minx, y=miny, w=(maxx - minx + 1), h=(maxy - miny + 1))

            # Filter: exclude huge background blobs
            if area < 50:
                continue
            if bx.w > w * 0.9 and bx.h > h * 0.9:
                continue

            boxes.append(bx)

    # Merge boxes that are very close horizontally (digits can fragment)
    boxes = _merge_close_boxes(boxes)

    return boxes


def _merge_close_boxes(boxes: list[_Box]) -> list[_Box]:
    if not boxes:
        return []

    boxes = sorted(boxes, key=lambda b: b.x)
    out: list[_Box] = []
    cur = boxes[0]

    for b in boxes[1:]:
        gap = b.x - (cur.x + cur.w)
        vert_overlap = _overlap_ratio((cur.y, cur.y + cur.h), (b.y, b.y + b.h))

        if gap <= 40 and vert_overlap > 0.4:
            # merge
            minx = min(cur.x, b.x)
            miny = min(cur.y, b.y)
            maxx = max(cur.x + cur.w, b.x + b.w)
            maxy = max(cur.y + cur.h, b.y + b.h)
            cur = _Box(x=minx, y=miny, w=maxx - minx, h=maxy - miny)
        else:
            out.append(cur)
            cur = b

    out.append(cur)
    return out


def _overlap_ratio(a: tuple[int, int], b: tuple[int, int]) -> float:
    a0, a1 = a
    b0, b1 = b
    inter = max(0, min(a1, b1) - max(a0, b0))
    denom = max(1, min(a1 - a0, b1 - b0))
    return inter / denom


def _remove_small_components(bw: np.ndarray, min_area: int) -> np.ndarray:
    """Remove connected components smaller than min_area."""
    h, w = bw.shape
    visited = np.zeros_like(bw, dtype=np.uint8)
    out = bw.copy()

    for y in range(h):
        for x in range(w):
            if bw[y, x] == 0 or visited[y, x] == 1:
                continue
            q = [(x, y)]
            visited[y, x] = 1
            coords = []
            while q:
                cx, cy = q.pop()
                coords.append((cx, cy))
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < w and 0 <= ny < h:
                        if bw[ny, nx] == 1 and visited[ny, nx] == 0:
                            visited[ny, nx] = 1
                            q.append((nx, ny))

            if len(coords) < min_area:
                for cx, cy in coords:
                    out[cy, cx] = 0

    return out
