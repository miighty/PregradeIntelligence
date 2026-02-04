from __future__ import annotations

"""Centering measurement + overlay generation.

This module is v0: it aims to produce *stable* centering ratios + visuals.
We will iterate on robustness using real phone photos.

Approach (v0):
- Use the warped canonical image.
- Detect the outer card boundary (should align to canvas).
- Detect the inner artwork rectangle using edge detection + contour filtering.
- Compute margins and express as left/right and top/bottom percentages.

If inner artwork cannot be detected, we return conservative defaults and
flag failure in details.
"""

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

try:
    import cv2
except ImportError as e:
    raise ImportError(
        "opencv-python is required for centering measurement. "
        "Install with: pip install opencv-python"
    ) from e

from services.grading.centering_rules import psa_max_grade_by_centering


# Border detection constants
BORDER_SAMPLE_POSITIONS = 5  # Number of positions to sample along each edge
BORDER_MAX_WIDTH = 50  # Maximum expected border width in pixels (on canonical 744x1040)
BORDER_GRADIENT_THRESHOLD = 20  # Minimum brightness change to detect border edge
BORDER_MIN_WIDTH = 5  # Minimum expected border width


@dataclass(frozen=True)
class CenteringMeasurement:
    front_lr: tuple[float, float]
    front_tb: tuple[float, float]
    # In v0 we reuse the same measurement for back unless separately computed.
    back_lr: tuple[float, float]
    back_tb: tuple[float, float]
    psa_max: float
    details: dict[str, Any]


def _find_inner_artwork_rect(rgb: np.ndarray) -> Optional[tuple[int, int, int, int]]:
    """Return x,y,w,h of inner artwork rect, or None."""
    # Work in grayscale
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    # Reduce noise
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    # Edge detect
    edges = cv2.Canny(blur, 50, 150)

    # Morph close to connect
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    H, W = gray.shape
    image_area = float(H * W)

    best = None
    best_score = -1.0

    for cnt in contours:
        area = float(cv2.contourArea(cnt))
        if area < image_area * 0.05:
            continue

        rect = cv2.minAreaRect(cnt)
        (cx, cy), (rw, rh), angle = rect
        rw, rh = float(rw), float(rh)
        if rw <= 0 or rh <= 0:
            continue

        # Aspect should be reasonably rectangular (art box is wide-ish)
        aspect = min(rw / rh, rh / rw)
        if aspect < 0.55:
            continue

        # Prefer mid-large boxes not touching the border.
        box = cv2.boxPoints(rect).astype(np.int32)
        x, y, w, h = cv2.boundingRect(box)

        # Reject boxes that are basically the whole card
        area_ratio = (w * h) / image_area
        if area_ratio > 0.9:
            continue

        # Penalize proximity to edges (inner artwork should have margins)
        edge_pen = 0.0
        pad = int(min(H, W) * 0.02)
        if x < pad or y < pad or (x + w) > (W - pad) or (y + h) > (H - pad):
            edge_pen = 0.2

        score = area_ratio - edge_pen
        if score > best_score:
            best_score = score
            best = (x, y, w, h)

    return best


def _lr_tb_from_rect(card_w: int, card_h: int, rect: tuple[int, int, int, int]) -> tuple[tuple[float, float], tuple[float, float]]:
    x, y, w, h = rect
    left = x
    right = card_w - (x + w)
    top = y
    bottom = card_h - (y + h)

    # Convert to percentages
    lr_total = left + right
    tb_total = top + bottom

    # Avoid div0
    if lr_total <= 0:
        lr = (50.0, 50.0)
    else:
        lr = (left / lr_total * 100.0, right / lr_total * 100.0)

    if tb_total <= 0:
        tb = (50.0, 50.0)
    else:
        tb = (top / tb_total * 100.0, bottom / tb_total * 100.0)

    return lr, tb


def _lr_tb_from_center(card_w: int, card_h: int, cx: float, cy: float) -> tuple[tuple[float, float], tuple[float, float]]:
    # Convert a center offset into a pseudo "margins" ratio.
    # If center is perfect: 50/50.
    # If center shifts to the right: left margin grows, right margin shrinks, etc.
    dx = (cx - (card_w / 2.0)) / (card_w / 2.0)
    dy = (cy - (card_h / 2.0)) / (card_h / 2.0)

    left = 50.0 + (dx * 50.0)
    right = 100.0 - left

    top = 50.0 + (dy * 50.0)
    bottom = 100.0 - top

    # clamp
    left = float(max(0.0, min(100.0, left)))
    right = float(max(0.0, min(100.0, right)))
    top = float(max(0.0, min(100.0, top)))
    bottom = float(max(0.0, min(100.0, bottom)))

    return (left, right), (top, bottom)


def _detect_pokeball_center(rgb: np.ndarray) -> Optional[tuple[float, float, float]]:
    """Try to locate the Pokemon back Pokéball via circle detection.

    Returns (cx, cy, r) or None.
    """
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (9, 9), 2)

    H, W = gray.shape

    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=min(H, W) * 0.25,
        param1=120,
        param2=35,
        minRadius=int(min(H, W) * 0.12),
        maxRadius=int(min(H, W) * 0.32),
    )

    if circles is None:
        return None

    circles = circles[0]

    best = None
    best_score = -1.0
    for (cx, cy, r) in circles:
        # prefer circles near center
        nd = ((cx - W / 2) ** 2 + (cy - H / 2) ** 2) ** 0.5
        nd /= (W**2 + H**2) ** 0.5
        score = (1.0 - nd) + (r / max(H, W))
        if score > best_score:
            best_score = score
            best = (float(cx), float(cy), float(r))

    return best


def _find_border_edge(profile: np.ndarray, from_edge: bool = True) -> int:
    """Find where the border transitions to artwork in a 1D brightness profile.
    
    Args:
        profile: 1D array of brightness values from edge to center
        from_edge: If True, scan from edge inward; if False, scan from center outward
    
    Returns:
        Pixel position where border ends (or 0 if not found)
    """
    if len(profile) < BORDER_MIN_WIDTH:
        return 0
    
    # Compute gradient (difference between adjacent pixels)
    gradient = np.abs(np.diff(profile.astype(np.float32)))
    
    # Look for significant brightness change within expected border region
    search_range = min(BORDER_MAX_WIDTH, len(gradient))
    
    for i in range(BORDER_MIN_WIDTH, search_range):
        # Check if there's a significant gradient at this position
        if gradient[i] > BORDER_GRADIENT_THRESHOLD:
            # Verify this is a sustained edge (not noise) by checking neighbors
            window_start = max(0, i - 2)
            window_end = min(len(gradient), i + 3)
            if np.max(gradient[window_start:window_end]) > BORDER_GRADIENT_THRESHOLD:
                return i
    
    return 0


def _measure_border_widths(rgb: np.ndarray) -> Optional[dict[str, float]]:
    """Measure physical border width on each side by detecting color/brightness transitions.
    
    This approach measures the actual border by finding where the uniform border
    color transitions to the card artwork.
    
    Args:
        rgb: RGB image array
    
    Returns:
        Dictionary with border widths {"left": px, "right": px, "top": px, "bottom": px}
        or None if detection fails
    """
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    H, W = gray.shape
    
    # Sample at multiple Y positions for left/right borders
    sample_ys = [int(H * (i + 1) / (BORDER_SAMPLE_POSITIONS + 1)) for i in range(BORDER_SAMPLE_POSITIONS)]
    # Sample at multiple X positions for top/bottom borders
    sample_xs = [int(W * (i + 1) / (BORDER_SAMPLE_POSITIONS + 1)) for i in range(BORDER_SAMPLE_POSITIONS)]
    
    left_widths = []
    right_widths = []
    top_widths = []
    bottom_widths = []
    
    # Measure left and right borders
    for y in sample_ys:
        # Left border: scan from left edge inward
        left_profile = gray[y, :BORDER_MAX_WIDTH]
        left_edge = _find_border_edge(left_profile)
        if left_edge > 0:
            left_widths.append(left_edge)
        
        # Right border: scan from right edge inward
        right_profile = gray[y, -BORDER_MAX_WIDTH:][::-1]  # Reverse for inward scan
        right_edge = _find_border_edge(right_profile)
        if right_edge > 0:
            right_widths.append(right_edge)
    
    # Measure top and bottom borders
    for x in sample_xs:
        # Top border: scan from top edge inward
        top_profile = gray[:BORDER_MAX_WIDTH, x]
        top_edge = _find_border_edge(top_profile)
        if top_edge > 0:
            top_widths.append(top_edge)
        
        # Bottom border: scan from bottom edge inward
        bottom_profile = gray[-BORDER_MAX_WIDTH:, x][::-1]  # Reverse for inward scan
        bottom_edge = _find_border_edge(bottom_profile)
        if bottom_edge > 0:
            bottom_widths.append(bottom_edge)
    
    # Need at least some measurements on each side
    if not (left_widths and right_widths and top_widths and bottom_widths):
        return None
    
    # Use median to be robust to outliers
    return {
        "left": float(np.median(left_widths)),
        "right": float(np.median(right_widths)),
        "top": float(np.median(top_widths)),
        "bottom": float(np.median(bottom_widths)),
    }


def _lr_tb_from_borders(borders: dict[str, float]) -> tuple[tuple[float, float], tuple[float, float]]:
    """Convert border widths to LR/TB centering ratios.
    
    Args:
        borders: {"left": px, "right": px, "top": px, "bottom": px}
    
    Returns:
        ((left%, right%), (top%, bottom%))
    """
    lr_total = borders["left"] + borders["right"]
    tb_total = borders["top"] + borders["bottom"]
    
    if lr_total <= 0:
        lr = (50.0, 50.0)
    else:
        lr = (borders["left"] / lr_total * 100.0, borders["right"] / lr_total * 100.0)
    
    if tb_total <= 0:
        tb = (50.0, 50.0)
    else:
        tb = (borders["top"] / tb_total * 100.0, borders["bottom"] / tb_total * 100.0)
    
    return lr, tb


def measure_centering(front: Image.Image, back: Image.Image) -> CenteringMeasurement:
    front_rgb = np.array(front.convert("RGB"))
    back_rgb = np.array(back.convert("RGB"))

    fh, fw = front_rgb.shape[:2]

    # Try border-based measurement first (most reliable for physical centering)
    front_borders = _measure_border_widths(front_rgb)
    
    # Fallback: inner artwork rect detection
    front_rect = _find_inner_artwork_rect(front_rgb)
    back_rect = _find_inner_artwork_rect(back_rgb)

    details: dict[str, Any] = {
        "front_borders": front_borders,
        "front_inner_rect": front_rect,
        "back_inner_rect": back_rect,
        "back_pokeball": None,
        "back_method": None,
        "front_method": None,
    }

    # Front: PRIORITIZE border measurement (measures physical card border)
    # Fall back to inner rect if border detection fails
    if front_borders is not None:
        front_lr, front_tb = _lr_tb_from_borders(front_borders)
        details["front_detected"] = True
        details["front_method"] = "border"
    elif front_rect is not None:
        front_lr, front_tb = _lr_tb_from_rect(fw, fh, front_rect)
        details["front_detected"] = True
        details["front_method"] = "inner_rect"
    else:
        front_lr, front_tb = (50.0, 50.0), (50.0, 50.0)
        details["front_detected"] = False
        details["front_method"] = "none"

    def _rect_valid(rect: tuple[int, int, int, int]) -> bool:
        x, y, w, h = rect
        if w <= 0 or h <= 0:
            return False
        if x < 0 or y < 0:
            return False
        if (x + w) > fw or (y + h) > fh:
            return False
        return True

    # Back: PRIORITIZE Pokeball detection (most reliable for standard Pokemon backs)
    # Only fall back to inner_rect if Pokeball detection fails
    pb = _detect_pokeball_center(back_rgb)
    details["back_pokeball"] = pb
    
    if pb is not None:
        cx, cy, r = pb
        back_lr, back_tb = _lr_tb_from_center(fw, fh, cx, cy)
        details["back_detected"] = True
        details["back_method"] = "pokeball"
    elif back_rect is not None and _rect_valid(back_rect):
        # Fallback to inner rect only if Pokeball not found
        back_lr, back_tb = _lr_tb_from_rect(fw, fh, back_rect)
        details["back_detected"] = True
        details["back_method"] = "inner_rect"
        if back_rect is not None and not _rect_valid(back_rect):
            details["back_inner_rect_invalid"] = True
    else:
        back_lr, back_tb = (50.0, 50.0), (50.0, 50.0)
        details["back_detected"] = False
        details["back_method"] = "none"

    psa_max = psa_max_grade_by_centering(front_lr, front_tb, back_lr, back_tb)

    return CenteringMeasurement(
        front_lr=front_lr,
        front_tb=front_tb,
        back_lr=back_lr,
        back_tb=back_tb,
        psa_max=psa_max,
        details=details,
    )


def render_centering_overlay(
    image: Image.Image,
    inner_rect: Optional[tuple[int, int, int, int]],
    lr: tuple[float, float],
    tb: tuple[float, float],
    title: str,
    pokeball: Optional[tuple[float, float, float]] = None,
) -> Image.Image:
    out = image.convert("RGB").copy()
    draw = ImageDraw.Draw(out)

    w, h = out.size

    # Outer border
    draw.rectangle([2, 2, w - 3, h - 3], outline=(0, 255, 0), width=2)

    if inner_rect is not None:
        x, y, iw, ih = inner_rect
        draw.rectangle([x, y, x + iw, y + ih], outline=(255, 0, 0), width=3)

        # center lines
        cx = x + iw / 2
        cy = y + ih / 2
        draw.line([cx, 0, cx, h], fill=(255, 0, 0), width=2)
        draw.line([0, cy, w, cy], fill=(255, 0, 0), width=2)

    if pokeball is not None:
        cx, cy, r = pokeball
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(0, 200, 255), width=3)
        draw.line([cx, 0, cx, h], fill=(0, 200, 255), width=2)
        draw.line([0, cy, w, cy], fill=(0, 200, 255), width=2)

    # Text
    text = (
        f"{title}\n"
        f"LR: {lr[0]:.1f}/{lr[1]:.1f} (max side {max(lr):.1f})\n"
        f"TB: {tb[0]:.1f}/{tb[1]:.1f} (max side {max(tb):.1f})"
    )

    # Use default font (no dependency)
    draw.rectangle([8, 8, 8 + 520, 8 + 70], fill=(0, 0, 0))
    draw.text((16, 14), text, fill=(255, 255, 255))

    return out
