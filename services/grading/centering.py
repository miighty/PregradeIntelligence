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
from services.card_warp import warp_card_best_effort


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
    """Return x,y,w,h of inner artwork rect, or None.

    We run a small multi-pass strategy because phone photos vary wildly.
    """

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    H, W = gray.shape
    if H < 10 or W < 10:
        return None

    image_area = float(H * W)

    # Try a few preprocessing + Canny thresholds.
    # (low, high, blur_ksize, morph_ksize)
    passes = [
        (40, 130, 5, 5),
        (50, 150, 5, 5),
        (60, 180, 5, 7),
        (40, 120, 7, 7),
    ]

    best = None
    best_score = -1e9

    for low, high, blur_k, morph_k in passes:
        blur = cv2.GaussianBlur(gray, (blur_k, blur_k), 0)
        edges = cv2.Canny(blur, low, high)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (morph_k, morph_k))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue

        for cnt in contours:
            area = float(cv2.contourArea(cnt))
            if area < image_area * 0.03:
                continue

            rect = cv2.minAreaRect(cnt)
            (cx, cy), (rw, rh), angle = rect
            rw, rh = float(rw), float(rh)
            if rw <= 0 or rh <= 0:
                continue

            # Aspect should be reasonably rectangular.
            aspect = min(rw / rh, rh / rw)
            if aspect < 0.45:
                continue

            box = cv2.boxPoints(rect).astype(np.int32)
            x, y, w, h = cv2.boundingRect(box)

            area_ratio = (w * h) / image_area
            # Inner content should not be the whole card.
            if area_ratio > 0.92:
                continue

            # Penalize proximity to edges (inner artwork should have margins)
            pad = int(min(H, W) * 0.015)
            edge_pen = 0.0
            if x < pad or y < pad or (x + w) > (W - pad) or (y + h) > (H - pad):
                edge_pen = 0.25

            # Prefer boxes that are medium-large (typical inner frame on fronts)
            # and not extremely thin.
            thin_pen = 0.0
            if w < W * 0.25 or h < H * 0.25:
                thin_pen = 0.35

            score = area_ratio - edge_pen - thin_pen
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


def _rect_area_ratio(rect: Optional[tuple[int, int, int, int]], w: int, h: int) -> float:
    if rect is None:
        return 0.0
    x, y, rw, rh = rect
    if rw <= 0 or rh <= 0:
        return 0.0
    return float(rw * rh) / float(w * h)


def measure_centering(front: Image.Image, back: Image.Image) -> CenteringMeasurement:
    # Re-warp inside centering as a robustness layer.
    # This reduces the need for the user to tightly frame/zoom the card.
    f_warped, f_warp_used, f_warp_reason, _ = warp_card_best_effort(front.convert("RGB"))
    b_warped, b_warp_used, b_warp_reason, _ = warp_card_best_effort(back.convert("RGB"))

    front_rgb = np.array(f_warped.convert("RGB"))
    back_rgb = np.array(b_warped.convert("RGB"))

    fh, fw = front_rgb.shape[:2]

    front_rect = _find_inner_artwork_rect(front_rgb)
    back_rect = _find_inner_artwork_rect(back_rgb)

    details: dict[str, Any] = {
        "front_warp_used": f_warp_used,
        "front_warp_reason": f_warp_reason,
        "back_warp_used": b_warp_used,
        "back_warp_reason": b_warp_reason,
        "front_inner_rect": front_rect,
        "back_inner_rect": back_rect,
        "front_inner_rect_area_ratio": _rect_area_ratio(front_rect, fw, fh),
        "back_inner_rect_area_ratio": _rect_area_ratio(back_rect, fw, fh),
        "back_pokeball": None,
        "back_method": None,
    }

    # Front: prefer artwork rect. If we can't detect it, DO NOT assume perfect centering.
    if front_rect is None:
        # Mark unknown; we keep 50/50 ratios for display but will cap PSA max later.
        front_lr, front_tb = (50.0, 50.0), (50.0, 50.0)
        details["front_detected"] = False
        details["front_method"] = "none"
    else:
        front_lr, front_tb = _lr_tb_from_rect(fw, fh, front_rect)
        details["front_detected"] = True
        details["front_method"] = "inner_rect"

        # Reliability checks: if the detected rect is suspicious (too big/small), treat as unreliable.
        ar = details.get("front_inner_rect_area_ratio", 0.0)
        if ar < 0.10 or ar > 0.85:
            details["front_centering_unreliable"] = True

    def _rect_valid(rect: tuple[int, int, int, int]) -> bool:
        x, y, w, h = rect
        if w <= 0 or h <= 0:
            return False
        if x < 0 or y < 0:
            return False
        if (x + w) > fw or (y + h) > fh:
            return False
        return True

    # Back: prefer inner rect if it is valid; otherwise fall back to pokeball.
    if back_rect is not None and _rect_valid(back_rect):
        back_lr, back_tb = _lr_tb_from_rect(fw, fh, back_rect)
        details["back_detected"] = True
        details["back_method"] = "inner_rect"
    else:
        if back_rect is not None and not _rect_valid(back_rect):
            details["back_inner_rect_invalid"] = True
        pb = _detect_pokeball_center(back_rgb)
        details["back_pokeball"] = pb
        if pb is not None:
            cx, cy, r = pb
            back_lr, back_tb = _lr_tb_from_center(fw, fh, cx, cy)
            details["back_detected"] = True
            details["back_method"] = "pokeball"
        else:
            back_lr, back_tb = (50.0, 50.0), (50.0, 50.0)
            details["back_detected"] = False
            details["back_method"] = "none"

    psa_max = psa_max_grade_by_centering(front_lr, front_tb, back_lr, back_tb)

    # If we failed to detect the front inner frame (or detection is flagged unreliable),
    # we cannot score centering reliably.
    # Be conservative: cap to PSA 8 (still allows good cards but prevents fake PSA10 inflation).
    if (not details.get("front_detected", False)) or details.get("front_centering_unreliable", False):
        psa_max = min(psa_max, 8)
        details["front_centering_unreliable"] = True

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
    warp_used: Optional[bool] = None,
    warp_reason: Optional[str] = None,
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
    warp_line = ""
    if warp_used is not None:
        warp_line = f"\nwarp: {'yes' if warp_used else 'no'} ({warp_reason or ''})"

    text = (
        f"{title}\n"
        f"LR: {lr[0]:.1f}/{lr[1]:.1f} (max side {max(lr):.1f})\n"
        f"TB: {tb[0]:.1f}/{tb[1]:.1f} (max side {max(tb):.1f})"
        f"{warp_line}"
    )

    # Use default font (no dependency)
    draw.rectangle([8, 8, 8 + 520, 8 + 70], fill=(0, 0, 0))
    draw.text((16, 14), text, fill=(255, 255, 255))

    return out
