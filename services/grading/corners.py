from __future__ import annotations

"""Corner defect detection.

Detects whitening, bends, and flattening at card corners using deterministic
heuristics on canonical images.

Approach:
1. Extract corner patches from the canonical image.
2. Analyze local brightness/saturation variance to detect whitening.
3. Measure edge curvature to detect flattening or rounding.
4. Return severity scores [0..1] and per-corner evidence for explainability.

All thresholds are fixed constants for determinism and explainability.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image

try:
    import cv2
except ImportError as e:
    raise ImportError(
        "opencv-python is required for corner detection. "
        "Install with: pip install opencv-python"
    ) from e


# Corner patch size as fraction of canonical dimensions (744x1040)
CORNER_PATCH_FRACTION = 0.08  # ~60x80 pixels

# Whitening detection thresholds
WHITENING_BRIGHTNESS_THRESHOLD = 200  # Pixels above this are considered "white"
WHITENING_RATIO_MINOR = 0.15  # >15% white pixels = minor whitening
WHITENING_RATIO_MODERATE = 0.30  # >30% = moderate
WHITENING_RATIO_SIGNIFICANT = 0.50  # >50% = significant

# Flattening detection: expected corner should have some curvature
# Lower variance in edge angles indicates flattening
EDGE_VARIANCE_FLAT_THRESHOLD = 0.02  # Below this = flattened corner


@dataclass(frozen=True)
class CornerAnalysis:
    """Analysis result for a single corner."""
    name: str  # e.g., "top_left", "top_right", "bottom_left", "bottom_right"
    whitening_ratio: float  # 0..1, fraction of bright pixels
    brightness_mean: float  # Mean brightness in corner patch
    brightness_std: float  # Std of brightness
    edge_variance: float  # Variance of edge angles (curvature proxy)
    severity: float  # Combined severity 0..1


@dataclass(frozen=True)
class CornersResult:
    """Complete corners analysis result."""
    severity: float  # Overall severity 0..1
    per_corner: tuple[CornerAnalysis, ...]
    details: dict[str, Any]


def _extract_corner_patch(
    img: np.ndarray,
    corner: str,
    patch_w: int,
    patch_h: int,
) -> np.ndarray:
    """Extract a corner patch from the image."""
    h, w = img.shape[:2]
    
    if corner == "top_left":
        return img[0:patch_h, 0:patch_w]
    elif corner == "top_right":
        return img[0:patch_h, w - patch_w:w]
    elif corner == "bottom_left":
        return img[h - patch_h:h, 0:patch_w]
    elif corner == "bottom_right":
        return img[h - patch_h:h, w - patch_w:w]
    else:
        raise ValueError(f"Unknown corner: {corner}")


def _analyze_whitening(patch: np.ndarray) -> tuple[float, float, float]:
    """Analyze whitening in a corner patch.
    
    Returns:
        (whitening_ratio, brightness_mean, brightness_std)
    """
    # Convert to grayscale if needed
    if len(patch.shape) == 3:
        gray = cv2.cvtColor(patch, cv2.COLOR_RGB2GRAY)
    else:
        gray = patch
    
    # Count pixels above brightness threshold
    total_pixels = gray.size
    white_pixels = np.sum(gray > WHITENING_BRIGHTNESS_THRESHOLD)
    whitening_ratio = float(white_pixels) / float(total_pixels) if total_pixels > 0 else 0.0
    
    brightness_mean = float(np.mean(gray))
    brightness_std = float(np.std(gray))
    
    return whitening_ratio, brightness_mean, brightness_std


def _analyze_edge_curvature(patch: np.ndarray) -> float:
    """Analyze edge curvature to detect flattening.
    
    Returns variance of edge directions as a proxy for curvature.
    Low variance = flat edges, high variance = curved/natural corner.
    """
    # Convert to grayscale
    if len(patch.shape) == 3:
        gray = cv2.cvtColor(patch, cv2.COLOR_RGB2GRAY)
    else:
        gray = patch
    
    # Compute gradients
    sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    
    # Compute edge angles where gradient magnitude is significant
    magnitude = np.sqrt(sobelx**2 + sobely**2)
    threshold = np.percentile(magnitude, 75)  # Top 25% edges
    
    mask = magnitude > threshold
    if np.sum(mask) < 10:
        # Not enough edges to analyze
        return 0.5  # Neutral
    
    angles = np.arctan2(sobely[mask], sobelx[mask])
    
    # Circular variance for angles
    sin_sum = np.sum(np.sin(angles))
    cos_sum = np.sum(np.cos(angles))
    n = len(angles)
    
    r = np.sqrt(sin_sum**2 + cos_sum**2) / n
    circular_variance = 1.0 - r  # 0 = all same direction, 1 = uniform
    
    return float(circular_variance)


def _compute_corner_severity(
    whitening_ratio: float,
    edge_variance: float,
) -> float:
    """Compute combined severity for a corner.
    
    Both whitening and flattening contribute to severity.
    """
    # Whitening contribution
    if whitening_ratio >= WHITENING_RATIO_SIGNIFICANT:
        whitening_severity = 1.0
    elif whitening_ratio >= WHITENING_RATIO_MODERATE:
        whitening_severity = 0.6
    elif whitening_ratio >= WHITENING_RATIO_MINOR:
        whitening_severity = 0.3
    else:
        whitening_severity = whitening_ratio / WHITENING_RATIO_MINOR * 0.3
    
    # Flattening contribution (low variance = flat = bad)
    if edge_variance < EDGE_VARIANCE_FLAT_THRESHOLD:
        flat_severity = 0.4
    else:
        flat_severity = 0.0
    
    # Combined: whitening is primary, flattening adds
    severity = min(1.0, whitening_severity + flat_severity * 0.5)
    
    return severity


def detect_corner_defects(image: Image.Image) -> CornersResult:
    """Detect corner defects in a canonical card image.
    
    Args:
        image: Canonical RGB image (744x1040)
    
    Returns:
        CornersResult with severity and per-corner analysis
    """
    rgb = np.array(image.convert("RGB"))
    h, w = rgb.shape[:2]
    
    patch_w = int(w * CORNER_PATCH_FRACTION)
    patch_h = int(h * CORNER_PATCH_FRACTION)
    
    corners = ["top_left", "top_right", "bottom_left", "bottom_right"]
    analyses = []
    
    for corner_name in corners:
        patch = _extract_corner_patch(rgb, corner_name, patch_w, patch_h)
        
        whitening_ratio, brightness_mean, brightness_std = _analyze_whitening(patch)
        edge_variance = _analyze_edge_curvature(patch)
        severity = _compute_corner_severity(whitening_ratio, edge_variance)
        
        analysis = CornerAnalysis(
            name=corner_name,
            whitening_ratio=whitening_ratio,
            brightness_mean=brightness_mean,
            brightness_std=brightness_std,
            edge_variance=edge_variance,
            severity=severity,
        )
        analyses.append(analysis)
    
    # Overall severity: max of individual corners (worst corner dominates)
    overall_severity = max(a.severity for a in analyses)
    
    details = {
        "patch_size": (patch_w, patch_h),
        "thresholds": {
            "whitening_brightness": WHITENING_BRIGHTNESS_THRESHOLD,
            "whitening_ratio_minor": WHITENING_RATIO_MINOR,
            "whitening_ratio_moderate": WHITENING_RATIO_MODERATE,
            "whitening_ratio_significant": WHITENING_RATIO_SIGNIFICANT,
            "edge_variance_flat": EDGE_VARIANCE_FLAT_THRESHOLD,
        },
        "per_corner_summary": {
            a.name: {
                "whitening_ratio": round(a.whitening_ratio, 4),
                "severity": round(a.severity, 4),
            }
            for a in analyses
        },
    }
    
    return CornersResult(
        severity=overall_severity,
        per_corner=tuple(analyses),
        details=details,
    )
