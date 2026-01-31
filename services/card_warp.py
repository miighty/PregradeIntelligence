"""Card rectangle detection + perspective warp utilities.

Goal: normalize real-world phone photos to a consistent card frame.
Deterministic, lightweight (OpenCV only), and fast enough for local runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, List

try:
    import cv2
except ImportError as e:
    raise ImportError(
        "opencv-python is required for card_warp. "
        "Install with: pip install opencv-python>=4.9.0"
    ) from e

import numpy as np
from PIL import Image


# Pokemon card aspect ratio: 63mm / 88mm = 0.716 (portrait)
_CARD_ASPECT_TARGET = 63.0 / 88.0  # ~0.716

# Hard gates for candidate acceptance (strict band)
_ASPECT_MIN_STRICT = 0.66  # Tight: reject square-ish blobs
_ASPECT_MAX_STRICT = 0.78  # Tight: reject overly wide shapes
# Relaxed band used only if no strict candidates found
_ASPECT_MIN_RELAXED = 0.58
_ASPECT_MAX_RELAXED = 0.84

_MIN_AREA_RATIO = 0.08  # Reject tiny blobs that can't be real cards
_MAX_AREA_RATIO = 0.97  # Reject quads that are basically the whole image (likely frame)
_MIN_RECTANGULARITY = 0.70


@dataclass(frozen=True)
class QuadCandidate:
    quad: np.ndarray
    score: float
    area: float
    aspect: float
    rectangularity: float
    area_ratio: float
    center_dist: float  # Distance from image center (normalized 0-1)
    source: str
    pipeline: str


def detect_card_quad(pil_image: Image.Image) -> tuple[Optional[np.ndarray], dict[str, Any]]:
    """Detect the card quadrilateral from a photo.

    Returns (quad, debug). quad is a 4x2 array of points or None.
    Uses multiple preprocessing pipelines and picks the best scoring quad.
    """
    rgb = pil_image.convert("RGB")
    bgr = cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    img_h, img_w = gray.shape
    image_area = float(img_h * img_w)
    image_center = (img_w / 2.0, img_h / 2.0)
    # Diagonal for normalizing center distance
    image_diag = float(np.sqrt(img_w**2 + img_h**2))

    # Multi-preprocess pipelines for robustness under glare/sleeves
    edge_maps = _generate_edge_maps(gray)

    all_candidates: List[QuadCandidate] = []

    for pipeline_name, edges in edge_maps:
        # Apply morphological closing to connect fragmented edges
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = _score_contours(contours, image_area, image_center, image_diag, pipeline_name)
        all_candidates.extend(candidates)

    # Try strict gates first; if none pass, try relaxed gates
    strict_gated = [c for c in all_candidates if _passes_gates(c, strict=True)]
    if strict_gated:
        best = max(strict_gated, key=lambda c: c.score)
        return best.quad, _debug_payload(best, len(all_candidates), len(strict_gated), gate_mode="strict")

    relaxed_gated = [c for c in all_candidates if _passes_gates(c, strict=False)]
    if relaxed_gated:
        best = max(relaxed_gated, key=lambda c: c.score)
        return best.quad, _debug_payload(best, len(all_candidates), len(relaxed_gated), gate_mode="relaxed")

    # If no gated candidates but we have some candidates, report the best one for debugging
    best_ungated = max(all_candidates, key=lambda c: c.score) if all_candidates else None

    # Fallback: minAreaRect on largest contour from each pipeline, but only if it passes strict gates
    for pipeline_name, edges in edge_maps:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        largest = max(contours, key=cv2.contourArea)
        fallback = _try_min_area_rect(largest, image_area, image_center, image_diag, pipeline_name)
        # Only accept minAreaRect if it passes strict gates
        if fallback and _passes_gates(fallback, strict=True):
            return fallback.quad, _debug_payload(fallback, len(all_candidates), 0, gate_mode="strict_fallback")

    # Return diagnostic info about why we failed
    debug_info: dict[str, Any] = {
        "method": "none",
        "reason": "no_valid_quad",
        "candidates_total": len(all_candidates),
    }
    
    # Add gate failure breakdown
    gate_failure_info = _compute_gate_failures(all_candidates)
    debug_info["gate_failures"] = gate_failure_info["gate_failures"]
    debug_info["closest_rejected"] = gate_failure_info["closest_rejected"]
    
    if best_ungated:
        debug_info["best_rejected"] = {
            "aspect": round(best_ungated.aspect, 4),
            "area_ratio": round(best_ungated.area_ratio, 4),
            "rectangularity": round(best_ungated.rectangularity, 4),
            "center_dist": round(best_ungated.center_dist, 4),
            "score": round(best_ungated.score, 4),
            "pipeline": best_ungated.pipeline,
            "failed_aspect_strict": not (_ASPECT_MIN_STRICT <= best_ungated.aspect <= _ASPECT_MAX_STRICT),
            "failed_aspect_relaxed": not (_ASPECT_MIN_RELAXED <= best_ungated.aspect <= _ASPECT_MAX_RELAXED),
            "failed_area_min": best_ungated.area_ratio < _MIN_AREA_RATIO,
            "failed_area_max": best_ungated.area_ratio > _MAX_AREA_RATIO,
            "failed_rect": best_ungated.rectangularity < _MIN_RECTANGULARITY,
        }
    return None, debug_info


def _generate_edge_maps(gray: np.ndarray) -> List[tuple[str, np.ndarray]]:
    """Generate multiple edge maps from different preprocessing pipelines."""
    results: List[tuple[str, np.ndarray]] = []

    # Pipeline 1: blur + Canny (original)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges1 = cv2.Canny(blurred, 50, 150)
    results.append(("blur_canny", edges1))

    # Pipeline 2: CLAHE + Canny (contrast enhancement for glare)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    clahe_img = clahe.apply(gray)
    clahe_blur = cv2.GaussianBlur(clahe_img, (5, 5), 0)
    edges2 = cv2.Canny(clahe_blur, 50, 150)
    results.append(("clahe_canny", edges2))

    # Pipeline 3: adaptive threshold (good for varying lighting)
    adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
    results.append(("adaptive_thresh", adaptive))

    # Pipeline 4: Otsu threshold (good for bimodal images)
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    results.append(("otsu_thresh", otsu))

    # Pipeline 5: heavy blur + wider Canny (for noisy images)
    heavy_blur = cv2.GaussianBlur(gray, (9, 9), 0)
    edges5 = cv2.Canny(heavy_blur, 30, 100)
    results.append(("heavy_blur_canny", edges5))

    # Pipeline 6: bilateral filter + Canny (edge-preserving blur)
    bilateral = cv2.bilateralFilter(gray, 9, 75, 75)
    edges6 = cv2.Canny(bilateral, 50, 150)
    results.append(("bilateral_canny", edges6))

    return results


def _score_contours(
    contours,
    image_area: float,
    image_center: tuple[float, float],
    image_diag: float,
    pipeline: str,
) -> List[QuadCandidate]:
    """Score contours and return quad candidates."""
    candidates: List[QuadCandidate] = []

    for cnt in contours:
        area = float(cv2.contourArea(cnt))
        area_ratio = area / image_area
        if area_ratio < 0.02:  # Quick filter for tiny contours
            continue

        peri = cv2.arcLength(cnt, True)
        
        # Try multiple epsilon values to find 4-point approximation
        quad = None
        for eps in [0.02, 0.03, 0.04, 0.05]:
            approx = cv2.approxPolyDP(cnt, eps * peri, True)
            if len(approx) == 4:
                quad = approx.reshape(4, 2).astype(np.float32)
                break
        
        # If no 4-point found, try convex hull
        if quad is None:
            hull = cv2.convexHull(cnt)
            hull_peri = cv2.arcLength(hull, True)
            for eps in [0.02, 0.03, 0.04, 0.05]:
                approx = cv2.approxPolyDP(hull, eps * hull_peri, True)
                if len(approx) == 4:
                    quad = approx.reshape(4, 2).astype(np.float32)
                    break
        
        if quad is None:
            continue

        ordered = order_corners(quad)
        width, height = _quad_size(ordered)
        if width < 20 or height < 20:
            continue

        # Compute aspect as min(w/h, h/w) so portrait/landscape both work
        aspect = min(width / height, height / width) if height > 0 and width > 0 else 0.0
        rectangularity = area / max(1.0, (width * height))

        # Compute center distance (normalized by image diagonal)
        quad_center = ordered.mean(axis=0)
        center_dist = float(np.linalg.norm(quad_center - np.array(image_center))) / image_diag

        # Scoring: proximity to ideal aspect + area (nonlinear) + rectangularity - center penalty
        aspect_score = 1.0 - min(abs(aspect - _CARD_ASPECT_TARGET) / _CARD_ASPECT_TARGET, 1.0)
        # Nonlinear area score: sqrt makes medium-large jumps matter more
        area_score = min(np.sqrt(area_ratio) * 1.5, 1.0)
        rect_score = min(rectangularity, 1.0)
        # Center penalty: prefer quads closer to image center (helps binder/multi-card)
        center_penalty = center_dist * 0.15

        # Weights: 0.40 area + 0.40 aspect + 0.20 rect, minus center penalty
        score = (area_score * 0.40) + (aspect_score * 0.40) + (rect_score * 0.20) - center_penalty

        candidates.append(
            QuadCandidate(
                quad=ordered,
                score=score,
                area=area,
                aspect=aspect,
                rectangularity=rectangularity,
                area_ratio=area_ratio,
                center_dist=center_dist,
                source="contour",
                pipeline=pipeline,
            )
        )

    return candidates


def _try_min_area_rect(
    contour,
    image_area: float,
    image_center: tuple[float, float],
    image_diag: float,
    pipeline: str,
) -> Optional[QuadCandidate]:
    """Try minAreaRect fallback, returning candidate if it passes basic checks."""
    area = float(cv2.contourArea(contour))
    area_ratio = area / image_area
    if area_ratio < 0.02:
        return None

    rect = cv2.minAreaRect(contour)
    box = cv2.boxPoints(rect).astype(np.float32)
    ordered = order_corners(box)
    width, height = _quad_size(ordered)

    if width < 20 or height < 20:
        return None

    aspect = min(width / height, height / width) if height > 0 and width > 0 else 0.0
    rectangularity = area / max(1.0, (width * height))

    # Compute center distance
    quad_center = ordered.mean(axis=0)
    center_dist = float(np.linalg.norm(quad_center - np.array(image_center))) / image_diag

    aspect_score = 1.0 - min(abs(aspect - _CARD_ASPECT_TARGET) / _CARD_ASPECT_TARGET, 1.0)
    area_score = min(np.sqrt(area_ratio) * 1.5, 1.0)
    rect_score = min(rectangularity, 1.0)
    center_penalty = center_dist * 0.15
    score = (area_score * 0.40) + (aspect_score * 0.40) + (rect_score * 0.20) - center_penalty

    return QuadCandidate(
        quad=ordered,
        score=score,
        area=area,
        aspect=aspect,
        rectangularity=rectangularity,
        area_ratio=area_ratio,
        center_dist=center_dist,
        source="minAreaRect",
        pipeline=pipeline,
    )


def _passes_gates(candidate: QuadCandidate, strict: bool = True) -> bool:
    """Check if candidate passes all hard gates.
    
    Args:
        candidate: The quad candidate to check.
        strict: If True, use tight aspect bounds; if False, use relaxed bounds.
    """
    if strict:
        aspect_min, aspect_max = _ASPECT_MIN_STRICT, _ASPECT_MAX_STRICT
    else:
        aspect_min, aspect_max = _ASPECT_MIN_RELAXED, _ASPECT_MAX_RELAXED

    if not (aspect_min <= candidate.aspect <= aspect_max):
        return False
    if candidate.area_ratio < _MIN_AREA_RATIO:
        return False
    if candidate.area_ratio > _MAX_AREA_RATIO:
        return False
    if candidate.rectangularity < _MIN_RECTANGULARITY:
        return False
    return True


def _compute_gate_failures(
    candidates: List[QuadCandidate],
) -> dict[str, Any]:
    """Compute per-gate failure counts and closest rejected candidate for each gate.
    
    Uses relaxed aspect bounds for aspect gate failure detection.
    Returns a dict with gate_failures (counts) and closest_rejected (best candidate per gate).
    """
    # Gate failure counters
    failed_aspect = 0
    failed_area_min = 0
    failed_area_max = 0
    failed_rect = 0
    
    # Closest candidate per gate (highest score among those failing that specific gate)
    closest_aspect: Optional[QuadCandidate] = None
    closest_area_min: Optional[QuadCandidate] = None
    closest_area_max: Optional[QuadCandidate] = None
    closest_rect: Optional[QuadCandidate] = None
    
    for c in candidates:
        # Check each gate individually (using relaxed aspect bounds)
        fails_aspect = not (_ASPECT_MIN_RELAXED <= c.aspect <= _ASPECT_MAX_RELAXED)
        fails_area_min = c.area_ratio < _MIN_AREA_RATIO
        fails_area_max = c.area_ratio > _MAX_AREA_RATIO
        fails_rect = c.rectangularity < _MIN_RECTANGULARITY
        
        if fails_aspect:
            failed_aspect += 1
            if closest_aspect is None or c.score > closest_aspect.score:
                closest_aspect = c
        if fails_area_min:
            failed_area_min += 1
            if closest_area_min is None or c.score > closest_area_min.score:
                closest_area_min = c
        if fails_area_max:
            failed_area_max += 1
            if closest_area_max is None or c.score > closest_area_max.score:
                closest_area_max = c
        if fails_rect:
            failed_rect += 1
            if closest_rect is None or c.score > closest_rect.score:
                closest_rect = c
    
    gate_failures = {
        "aspect": failed_aspect,
        "area_min": failed_area_min,
        "area_max": failed_area_max,
        "rectangularity": failed_rect,
    }
    
    def _candidate_summary(c: Optional[QuadCandidate]) -> Optional[dict[str, Any]]:
        if c is None:
            return None
        return {
            "aspect": round(c.aspect, 4),
            "area_ratio": round(c.area_ratio, 4),
            "rectangularity": round(c.rectangularity, 4),
            "center_dist": round(c.center_dist, 4),
            "score": round(c.score, 4),
            "pipeline": c.pipeline,
        }
    
    closest_rejected = {
        "aspect": _candidate_summary(closest_aspect),
        "area_min": _candidate_summary(closest_area_min),
        "area_max": _candidate_summary(closest_area_max),
        "rectangularity": _candidate_summary(closest_rect),
    }
    
    return {
        "gate_failures": gate_failures,
        "closest_rejected": closest_rejected,
    }


def order_corners(quad: np.ndarray) -> np.ndarray:
    """Return corners ordered as TL, TR, BR, BL."""
    if quad.shape != (4, 2):
        quad = quad.reshape(4, 2)

    s = quad.sum(axis=1)
    diff = np.diff(quad, axis=1).reshape(4)

    tl = quad[np.argmin(s)]
    br = quad[np.argmax(s)]
    tr = quad[np.argmin(diff)]
    bl = quad[np.argmax(diff)]

    return np.array([tl, tr, br, bl], dtype=np.float32)


def warp_card(pil_image: Image.Image, quad: np.ndarray, out_w: int = 744, out_h: int = 1040) -> Image.Image:
    """Perspective-warp the card to a fixed-size canonical frame."""
    rgb = pil_image.convert("RGB")
    bgr = cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)

    src = order_corners(quad).astype(np.float32)
    dst = np.array(
        [
            [0.0, 0.0],
            [float(out_w - 1), 0.0],
            [float(out_w - 1), float(out_h - 1)],
            [0.0, float(out_h - 1)],
        ],
        dtype=np.float32,
    )

    m = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(bgr, m, (out_w, out_h), flags=cv2.INTER_LINEAR)
    warped_rgb = cv2.cvtColor(warped, cv2.COLOR_BGR2RGB)
    return Image.fromarray(warped_rgb)


def detect_card_quad_with_candidates(
    pil_image: Image.Image,
) -> tuple[Optional[np.ndarray], dict[str, Any], List[QuadCandidate]]:
    """Detect card quad and return all candidates for debugging.
    
    Returns (quad, debug, all_candidates).
    """
    rgb = pil_image.convert("RGB")
    bgr = cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    img_h, img_w = gray.shape
    image_area = float(img_h * img_w)
    image_center = (img_w / 2.0, img_h / 2.0)
    image_diag = float(np.sqrt(img_w**2 + img_h**2))

    edge_maps = _generate_edge_maps(gray)
    all_candidates: List[QuadCandidate] = []

    for pipeline_name, edges in edge_maps:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = _score_contours(contours, image_area, image_center, image_diag, pipeline_name)
        all_candidates.extend(candidates)

    # Try strict gates first
    strict_gated = [c for c in all_candidates if _passes_gates(c, strict=True)]
    if strict_gated:
        best = max(strict_gated, key=lambda c: c.score)
        return best.quad, _debug_payload(best, len(all_candidates), len(strict_gated), gate_mode="strict"), all_candidates

    relaxed_gated = [c for c in all_candidates if _passes_gates(c, strict=False)]
    if relaxed_gated:
        best = max(relaxed_gated, key=lambda c: c.score)
        return best.quad, _debug_payload(best, len(all_candidates), len(relaxed_gated), gate_mode="relaxed"), all_candidates

    # Fallback: minAreaRect
    for pipeline_name, edges in edge_maps:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        largest = max(contours, key=cv2.contourArea)
        fallback = _try_min_area_rect(largest, image_area, image_center, image_diag, pipeline_name)
        if fallback and _passes_gates(fallback, strict=True):
            all_candidates.append(fallback)
            return fallback.quad, _debug_payload(fallback, len(all_candidates), 0, gate_mode="strict_fallback"), all_candidates

    debug_info: dict[str, Any] = {
        "method": "none",
        "reason": "no_valid_quad",
        "candidates_total": len(all_candidates),
    }
    
    # Add gate failure breakdown
    gate_failure_info = _compute_gate_failures(all_candidates)
    debug_info["gate_failures"] = gate_failure_info["gate_failures"]
    debug_info["closest_rejected"] = gate_failure_info["closest_rejected"]
    
    best_ungated = max(all_candidates, key=lambda c: c.score) if all_candidates else None
    if best_ungated:
        debug_info["best_rejected"] = {
            "aspect": round(best_ungated.aspect, 4),
            "area_ratio": round(best_ungated.area_ratio, 4),
            "rectangularity": round(best_ungated.rectangularity, 4),
            "center_dist": round(best_ungated.center_dist, 4),
            "score": round(best_ungated.score, 4),
            "pipeline": best_ungated.pipeline,
            "failed_aspect_strict": not (_ASPECT_MIN_STRICT <= best_ungated.aspect <= _ASPECT_MAX_STRICT),
            "failed_aspect_relaxed": not (_ASPECT_MIN_RELAXED <= best_ungated.aspect <= _ASPECT_MAX_RELAXED),
            "failed_area_min": best_ungated.area_ratio < _MIN_AREA_RATIO,
            "failed_area_max": best_ungated.area_ratio > _MAX_AREA_RATIO,
            "failed_rect": best_ungated.rectangularity < _MIN_RECTANGULARITY,
        }
    return None, debug_info, all_candidates


def warp_card_best_effort(pil_image: Image.Image) -> tuple[Image.Image, bool, str, dict[str, Any]]:
    """Try to warp the card; fall back to original image."""
    quad, debug = detect_card_quad(pil_image)
    if quad is None:
        return pil_image, False, "warp_not_found", debug

    try:
        warped = warp_card(pil_image, quad)
        method = debug.get("method", "unknown")
        pipeline = debug.get("pipeline", "unknown")
        return warped, True, f"warp_{method}_{pipeline}", debug
    except Exception:
        return pil_image, False, "warp_failed", debug


def _quad_size(quad: np.ndarray) -> tuple[float, float]:
    tl, tr, br, bl = quad
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    return float((width_a + width_b) / 2.0), float((height_a + height_b) / 2.0)


def _debug_payload(
    candidate: QuadCandidate,
    candidates_total: int,
    candidates_gated: int,
    gate_mode: str = "strict",
) -> dict[str, Any]:
    return {
        "method": candidate.source,
        "pipeline": candidate.pipeline,
        "score": round(candidate.score, 4),
        "area": round(candidate.area, 2),
        "area_ratio": round(candidate.area_ratio, 4),
        "aspect": round(candidate.aspect, 4),
        "rectangularity": round(candidate.rectangularity, 4),
        "center_dist": round(candidate.center_dist, 4),
        "candidates_total": candidates_total,
        "candidates_gated": candidates_gated,
        "gate_mode": gate_mode,
    }
