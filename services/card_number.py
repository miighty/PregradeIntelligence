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

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


@dataclass(frozen=True)
class ParsedNumber:
    number: str  # e.g. "6/95"
    confidence: float


# Common font paths on macOS/Linux. We'll try these and fall back to PIL default.
# Includes fonts similar to those used on Pokemon cards.
_FONT_CANDIDATES = [
    # Sans-serif bold fonts (most common on modern cards)
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/System/Library/Fonts/Supplemental/Helvetica Bold.ttf",
    "/System/Library/Fonts/Supplemental/Helvetica.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/Library/Fonts/Arial Black.ttf",
    # Futura (common in modern Pokemon cards)
    "/System/Library/Fonts/Supplemental/Futura.ttc",
    "/System/Library/Fonts/Supplemental/Futura Bold.ttf",
    "/Library/Fonts/Futura.ttc",
    # Gill Sans (used in older sets)
    "/System/Library/Fonts/Supplemental/Gill Sans.ttc",
    "/System/Library/Fonts/Supplemental/Gill Sans Bold.ttf",
    "/Library/Fonts/Gill Sans.ttc",
    # Impact (condensed, good for tight spaces)
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/Library/Fonts/Impact.ttf",
    # Standard sans-serif
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    # Linux fonts
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
]

# Multiple sizes to handle scaling variations
_FONT_SIZES = [44, 48, 52]


def parse_card_number_from_crop(crop: Image.Image) -> Optional[ParsedNumber]:
    """Parse x/yy from an already-cropped number region.

    Important: these number corners often include UI icons/background.
    We first try to auto-crop to the *darkest text blob* before segmentation.
    """
    # Normalize input
    img = crop.convert("L")

    # Increase contrast by stretching
    img = ImageOps.autocontrast(img)

    # Upscale aggressively
    w, h = img.size
    scale = 12
    img = img.resize((max(1, w * scale), max(1, h * scale)), resample=Image.Resampling.BICUBIC)

    arr = np.array(img, dtype=np.uint8)

    # Try multiple ROI strategies since number placement varies by card template.
    # Ordered by likelihood: bottom portion most common, then full, then top-left
    H, W = arr.shape
    
    roi_strategies = [
        ("bottom_third", arr[int(H * 0.67):, :]),  # Most common: number at very bottom
        ("bottom_half", arr[int(H * 0.5):, :]),     # Wider search if bottom-third fails
        ("full", arr),                              # Full image fallback
        ("top_left", arr[0 : int(H * 0.70), 0 : int(W * 0.80)]),  # Rare: scans with icons
    ]
    
    best_result: Optional[ParsedNumber] = None
    best_conf = -1.0
    
    # High confidence threshold for early exit
    EARLY_EXIT_CONF = 0.85
    
    for roi_name, roi in roi_strategies:
        result = _try_parse_roi(roi)
        if result and result.confidence > best_conf:
            best_conf = result.confidence
            best_result = result
            # Early exit if we have high confidence
            if best_conf >= EARLY_EXIT_CONF:
                break
    
    return best_result


def _try_parse_roi(roi: np.ndarray) -> Optional[ParsedNumber]:
    """Try to parse a card number from a single ROI.
    
    Uses multi-threshold binarization to handle varying backgrounds,
    with Otsu's method as a fallback for bimodal images.
    """
    if roi.size == 0:
        return None
    
    # Try multiple threshold percentiles to handle different backgrounds
    # Lower percentiles = darker threshold (for light backgrounds)
    # Higher percentiles = lighter threshold (for textured/holo backgrounds)
    # Ordered by likelihood: 5% is most common for standard cards
    threshold_percentiles = [5, 3, 10, 15]
    
    best_result: Optional[ParsedNumber] = None
    best_conf = -1.0
    
    # High confidence threshold for early exit
    EARLY_EXIT_CONF = 0.85
    
    for pct in threshold_percentiles:
        result = _try_parse_with_threshold(roi, pct)
        if result and result.confidence > best_conf:
            best_conf = result.confidence
            best_result = result
            # Early exit on high confidence
            if best_conf >= EARLY_EXIT_CONF:
                return best_result
    
    # Try Otsu's method as fallback (good for bimodal images like black text on light bg)
    otsu_result = _try_parse_with_otsu(roi)
    if otsu_result and otsu_result.confidence > best_conf:
        best_result = otsu_result
    
    return best_result


def _try_parse_with_otsu(roi: np.ndarray) -> Optional[ParsedNumber]:
    """Try to parse a card number using Otsu's binarization.
    
    Otsu's method automatically finds optimal threshold for bimodal images.
    """
    if roi.size == 0:
        return None
    
    # Otsu's threshold (inverted for dark text on light background)
    _, otsu_bw = cv2.threshold(roi, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    bw = otsu_bw.astype(np.uint8)

    # Morphological cleanup
    kernel = np.ones((3, 3), dtype=np.uint8)
    bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel)
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, kernel)

    # Auto-crop around ink
    bw, _ = _autocrop_to_ink(bw, roi)

    # Remove tiny specks
    bw = _remove_small_components(bw, min_area=25)

    boxes = _connected_component_boxes(bw)
    if not boxes:
        return None

    # Filter to likely glyphs: moderate size
    H2, W2 = bw.shape
    filtered: list[_Box] = []
    for b in boxes:
        if b.h < 10 or b.h > H2 * 0.9:
            continue
        if b.w < 8 or b.w > W2 * 0.95:
            continue
        filtered.append(b)

    # Split wide boxes
    split: list[_Box] = []
    for b in filtered:
        if b.w > b.h * 2.2:
            split.extend(_split_wide_box(bw, b))
        else:
            split.append(b)

    boxes = sorted(split, key=lambda b: b.x)
    if not boxes:
        return None

    glyphs: list[np.ndarray] = []
    for b in boxes:
        g = bw[b.y : b.y + b.h, b.x : b.x + b.w]
        if g.shape[1] < 8:
            continue
        glyphs.append(_render_glyph(g))

    if not glyphs:
        return None

    templates = _get_templates()

    # Collect matches with their confidence scores
    matches: list[tuple[str, float]] = []
    for g in glyphs:
        ch, score = _match_template(g, templates)
        if ch is None:
            continue
        matches.append((ch, score))

    if not matches:
        return None

    # Apply character normalizations
    matches = [(ch.replace("I", "1").replace("l", "1"), s) for ch, s in matches]

    # Use sliding window to find best number pattern
    result = _find_best_number_window(matches)
    if result is None:
        return None

    number, conf = result
    return ParsedNumber(number=number, confidence=round(conf, 2))


def _try_parse_with_threshold(roi: np.ndarray, percentile: int) -> Optional[ParsedNumber]:
    """Try to parse a card number using a specific threshold percentile."""
    if roi.size == 0:
        return None
    
    # Use threshold at given percentile to binarize
    t = int(np.percentile(roi, percentile))
    bw = (roi <= t).astype(np.uint8)  # 1 for ink

    # Morphological cleanup: remove noise and fill small holes
    kernel = np.ones((3, 3), dtype=np.uint8)
    bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel)   # remove noise specks
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, kernel)  # fill small holes in glyphs

    # Auto-crop around ink (drops backgrounds).
    bw, _ = _autocrop_to_ink(bw, roi)

    # Remove tiny specks (additional cleanup after morphology)
    bw = _remove_small_components(bw, min_area=25)

    boxes = _connected_component_boxes(bw)
    if not boxes:
        return None

    # Filter to likely glyphs: moderate size.
    H2, W2 = bw.shape
    filtered: list[_Box] = []
    for b in boxes:
        if b.h < 10 or b.h > H2 * 0.9:
            continue
        if b.w < 8 or b.w > W2 * 0.95:
            continue
        filtered.append(b)

    # Split any very wide boxes (often multiple glyphs stuck together)
    split: list[_Box] = []
    for b in filtered:
        if b.w > b.h * 2.2:
            split.extend(_split_wide_box(bw, b))
        else:
            split.append(b)

    boxes = sorted(split, key=lambda b: b.x)
    if not boxes:
        return None

    glyphs: list[np.ndarray] = []
    for b in boxes:
        g = bw[b.y : b.y + b.h, b.x : b.x + b.w]
        if g.shape[1] < 8:
            continue
        glyphs.append(_render_glyph(g))

    if not glyphs:
        return None

    templates = _get_templates()

    # Collect matches with their confidence scores
    matches: list[tuple[str, float]] = []
    for g in glyphs:
        ch, score = _match_template(g, templates)
        if ch is None:
            continue
        matches.append((ch, score))

    if not matches:
        return None

    # Apply character normalizations to handle common confusions
    matches = [(ch.replace("I", "1").replace("l", "1"), s) for ch, s in matches]

    # Use sliding window to find best number pattern, ignoring surrounding noise
    result = _find_best_number_window(matches)
    if result is None:
        return None

    number, conf = result
    return ParsedNumber(number=number, confidence=round(conf, 2))


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
    
    num = int(left)
    total = int(right)
    
    # Basic plausibility checks for Pokemon cards
    # Reject obviously invalid numbers
    if num <= 0 or total <= 0:
        return None
    # Most sets have at least 20 cards
    if total < 10:
        return None
    # Largest sets are around 300-400, allow up to 500 for promos/special
    if total > 500:
        return None
    # Card number shouldn't exceed total by too much (secret rares allow +150)
    if num > total + 150:
        return None
    
    return f"{num}/{total}"


def _calculate_number_confidence(number: str, match_scores: list[float]) -> float:
    """Calculate confidence for a detected number based on plausibility and match quality.
    
    Higher confidence for:
    - Numbers that pass all plausibility checks
    - Higher template match scores
    - Common set sizes (50-300)
    """
    if not number or "/" not in number:
        return 0.0
    
    parts = number.split("/")
    if len(parts) != 2:
        return 0.0
    
    try:
        num = int(parts[0])
        total = int(parts[1])
    except ValueError:
        return 0.0
    
    # Base confidence from template matching
    if match_scores:
        base_conf = sum(match_scores) / len(match_scores)
    else:
        base_conf = 0.5
    
    # Plausibility bonuses/penalties
    plausibility_score = 0.0
    
    # Common set sizes (most sets are 100-200)
    if 50 <= total <= 300:
        plausibility_score += 0.1
    elif 20 <= total <= 50 or 300 < total <= 400:
        plausibility_score += 0.05
    
    # Number within total (non-secret rare)
    if num <= total:
        plausibility_score += 0.05
    
    # Very plausible range for secret rares
    if total < num <= total + 50:
        plausibility_score += 0.02
    
    # Penalize edge cases
    if num > total + 100:
        plausibility_score -= 0.1
    if total < 20:
        plausibility_score -= 0.15
    
    return min(1.0, max(0.0, base_conf + plausibility_score))


def _find_best_number_window(
    matches: list[tuple[str, float]]
) -> Optional[tuple[str, float]]:
    """Find the best contiguous substring matching digit/digit pattern.
    
    Uses sliding window to find the highest-confidence valid "XXX/YYY" pattern,
    ignoring surrounding noise like set codes or symbols.
    
    Returns (number, confidence) for the best window, or None.
    """
    if len(matches) < 3:  # minimum: "X/Y"
        return None
    
    best_number: Optional[str] = None
    best_conf = -1.0
    best_scores: list[float] = []
    
    # Try all possible window sizes and positions
    # Window size 3-7 covers patterns like "1/9" to "999/999"
    for start in range(len(matches)):
        for end in range(start + 3, min(start + 8, len(matches) + 1)):
            window = matches[start:end]
            text = "".join(ch for ch, _ in window)
            
            # Check if this window forms a valid pattern (includes plausibility)
            parsed = _extract_number_pattern(text)
            if parsed:
                # Calculate confidence from this window's scores
                window_scores = [s for _, s in window if s > 0]
                if window_scores:
                    # Use improved confidence calculation with plausibility
                    conf = _calculate_number_confidence(parsed, window_scores)
                    if conf > best_conf:
                        best_conf = conf
                        best_number = parsed
                        best_scores = window_scores
    
    if best_number is None:
        return None
    
    # Final confidence adjustment based on match quality
    final_conf = _calculate_number_confidence(best_number, best_scores)
    return best_number, round(final_conf, 2)


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


# Confidence thresholds for template matching
_MATCH_THRESHOLD_HARD = 0.65  # Hard reject below this
_MATCH_THRESHOLD_SOFT = 0.60  # Soft accept (penalized) between soft and hard


def _match_template(g: np.ndarray, templates: dict[str, list[np.ndarray]]) -> tuple[Optional[str], float]:
    """Match a glyph against templates.
    
    Returns (char, score) where score is the confidence.
    Uses soft matching: scores between 0.60-0.65 are accepted but penalized.
    """
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

    # Hard reject below soft threshold
    if best_score < _MATCH_THRESHOLD_SOFT:
        return None, 0.0

    # Soft match: accept but penalize scores between soft and hard thresholds
    # This allows marginal matches to contribute if pattern validation succeeds
    if best_score < _MATCH_THRESHOLD_HARD:
        # Penalize soft matches by reducing their confidence
        penalized_score = best_score * 0.85
        return best_ch, float(penalized_score)

    return best_ch, float(best_score)


_TEMPLATES: Optional[dict[str, list[np.ndarray]]] = None


def _get_templates() -> dict[str, list[np.ndarray]]:
    global _TEMPLATES
    if _TEMPLATES is None:
        _TEMPLATES = _build_templates()
    return _TEMPLATES


def _build_templates() -> dict[str, list[np.ndarray]]:
    """Build glyph templates from multiple fonts at multiple sizes."""
    chars = list("0123456789/")

    fonts: list[ImageFont.FreeTypeFont | ImageFont.ImageFont] = []
    for p in _FONT_CANDIDATES:
        for size in _FONT_SIZES:
            try:
                fonts.append(ImageFont.truetype(p, size))
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

            # Filter: exclude tiny specks and huge background blobs
            if area < 30:
                continue
            if bx.w > w * 0.9 and bx.h > h * 0.9:
                continue

            # Drop long thin UI bars (common in HUD overlays) — unlikely to be digits.
            if bx.w > w * 0.45 and bx.h < h * 0.20:
                continue

            boxes.append(bx)

    # Merge boxes that are very close horizontally (digits can fragment)
    boxes = _merge_close_boxes(boxes)

    return boxes


def _split_wide_box(bw: np.ndarray, box: _Box) -> list[_Box]:
    """Split a wide box into multiple boxes using vertical ink projection."""
    region = bw[box.y : box.y + box.h, box.x : box.x + box.w]
    proj = region.sum(axis=0)

    # A "gap" is a run of columns with very little ink.
    gap_thresh = max(1, int(box.h * 0.03))
    gaps = proj <= gap_thresh

    # Find segments separated by gaps of at least a few pixels.
    min_gap = max(2, int(box.w * 0.015))
    min_seg = max(8, int(box.w * 0.03))

    segments: list[tuple[int, int]] = []
    start = 0
    i = 0
    while i < len(gaps):
        if gaps[i]:
            j = i
            while j < len(gaps) and gaps[j]:
                j += 1
            # gap from i..j
            if (j - i) >= min_gap:
                end = i
                if (end - start) >= min_seg:
                    segments.append((start, end))
                start = j
            i = j
        else:
            i += 1

    if (len(gaps) - start) >= min_seg:
        segments.append((start, len(gaps)))

    # If we failed to segment, return original.
    if len(segments) <= 1:
        return [box]

    out: list[_Box] = []
    for a, b in segments:
        # Tighten vertically within each segment
        seg = region[:, a:b]
        ys, xs = np.where(seg == 1)
        if len(xs) < 10:
            continue
        minx, maxx = int(xs.min()), int(xs.max())
        miny, maxy = int(ys.min()), int(ys.max())
        out.append(_Box(x=box.x + a + minx, y=box.y + miny, w=(maxx - minx + 1), h=(maxy - miny + 1)))

    return out or [box]


def _merge_close_boxes(boxes: list[_Box]) -> list[_Box]:
    # Conservative merge: keep characters separate unless clearly fragmented.

    if not boxes:
        return []

    boxes = sorted(boxes, key=lambda b: b.x)
    out: list[_Box] = []
    cur = boxes[0]

    for b in boxes[1:]:
        gap = b.x - (cur.x + cur.w)
        vert_overlap = _overlap_ratio((cur.y, cur.y + cur.h), (b.y, b.y + b.h))

        if gap <= 15 and vert_overlap > 0.4:
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


def _autocrop_to_ink(bw: np.ndarray, gray: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Crop to a tight-ish region containing ink.

    This helps when the corner crop includes UI icons or textured backgrounds.
    """
    ys, xs = np.where(bw == 1)
    if len(xs) < 50:
        return bw, gray

    minx, maxx = int(xs.min()), int(xs.max())
    miny, maxy = int(ys.min()), int(ys.max())

    # Pad a bit
    pad = 20
    minx = max(0, minx - pad)
    miny = max(0, miny - pad)
    maxx = min(bw.shape[1] - 1, maxx + pad)
    maxy = min(bw.shape[0] - 1, maxy + pad)

    bw2 = bw[miny : maxy + 1, minx : maxx + 1]
    gray2 = gray[miny : maxy + 1, minx : maxx + 1]
    return bw2, gray2


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
            coords: list[tuple[int, int]] = []
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
