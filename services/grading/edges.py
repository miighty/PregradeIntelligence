from __future__ import annotations

"""Edge defect detection.

Detects wear, chipping, and whitening along card edges using deterministic
heuristics on canonical images.

Approach:
1. Extract border bands along each edge.
2. Measure color uniformity to detect whitening/wear.
3. Detect high-frequency discontinuities for chipping.
4. Return severity scores [0..1] and per-edge evidence for explainability.

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
        "opencv-python is required for edge detection. "
        "Install with: pip install opencv-python"
    ) from e


# Border band width as fraction of card width/height
BORDER_BAND_FRACTION = 0.02  # ~15 pixels on 744 width

# Whitening thresholds (similar to corners)
WHITENING_BRIGHTNESS_THRESHOLD = 200
WHITENING_RATIO_MINOR = 0.20
WHITENING_RATIO_MODERATE = 0.35
WHITENING_RATIO_SIGNIFICANT = 0.55

# Chipping detection: high-frequency variation along edge
CHIPPING_STD_THRESHOLD_MINOR = 25.0  # Std dev of brightness along edge
CHIPPING_STD_THRESHOLD_MODERATE = 40.0
CHIPPING_STD_THRESHOLD_SIGNIFICANT = 60.0


@dataclass(frozen=True)
class EdgeAnalysis:
    """Analysis result for a single edge."""
    name: str  # "top", "bottom", "left", "right"
    whitening_ratio: float
    brightness_mean: float
    brightness_std: float  # Variation along the edge (chipping indicator)
    chipping_score: float  # Normalized chipping severity 0..1
    severity: float


@dataclass(frozen=True)
class EdgesResult:
    """Complete edges analysis result."""
    severity: float
    per_edge: tuple[EdgeAnalysis, ...]
    details: dict[str, Any]


def _extract_edge_band(
    img: np.ndarray,
    edge: str,
    band_width: int,
) -> np.ndarray:
    """Extract an edge band from the image."""
    h, w = img.shape[:2]
    
    if edge == "top":
        return img[0:band_width, :]
    elif edge == "bottom":
        return img[h - band_width:h, :]
    elif edge == "left":
        return img[:, 0:band_width]
    elif edge == "right":
        return img[:, w - band_width:w]
    else:
        raise ValueError(f"Unknown edge: {edge}")


def _analyze_edge_whitening(band: np.ndarray) -> tuple[float, float]:
    """Analyze whitening in an edge band.
    
    Returns:
        (whitening_ratio, brightness_mean)
    """
    if len(band.shape) == 3:
        gray = cv2.cvtColor(band, cv2.COLOR_RGB2GRAY)
    else:
        gray = band
    
    total_pixels = gray.size
    white_pixels = np.sum(gray > WHITENING_BRIGHTNESS_THRESHOLD)
    whitening_ratio = float(white_pixels) / float(total_pixels) if total_pixels > 0 else 0.0
    
    brightness_mean = float(np.mean(gray))
    
    return whitening_ratio, brightness_mean


def _analyze_chipping(band: np.ndarray, edge: str) -> float:
    """Analyze chipping by measuring brightness variation along the edge.
    
    Chipping appears as high-frequency brightness changes along the edge.
    Returns std deviation of brightness profile.
    """
    if len(band.shape) == 3:
        gray = cv2.cvtColor(band, cv2.COLOR_RGB2GRAY)
    else:
        gray = band
    
    # Project to 1D along the edge direction
    if edge in ("top", "bottom"):
        # Average across band width, get profile along length
        profile = np.mean(gray, axis=0)
    else:
        # Average across band width, get profile along height
        profile = np.mean(gray, axis=1)
    
    # High-pass filter to isolate high-frequency changes
    if len(profile) > 5:
        # Simple high-pass: subtract smoothed version
        smoothed = cv2.GaussianBlur(profile.reshape(-1, 1), (1, 5), 0).flatten()
        if len(smoothed) == len(profile):
            high_freq = np.abs(profile - smoothed)
            return float(np.std(high_freq))
    
    return float(np.std(profile))


def _compute_chipping_score(brightness_std: float) -> float:
    """Convert brightness std to chipping severity score."""
    if brightness_std >= CHIPPING_STD_THRESHOLD_SIGNIFICANT:
        return 1.0
    elif brightness_std >= CHIPPING_STD_THRESHOLD_MODERATE:
        return 0.6
    elif brightness_std >= CHIPPING_STD_THRESHOLD_MINOR:
        return 0.3
    else:
        return brightness_std / CHIPPING_STD_THRESHOLD_MINOR * 0.3


def _compute_edge_severity(whitening_ratio: float, chipping_score: float) -> float:
    """Compute combined severity for an edge."""
    # Whitening contribution
    if whitening_ratio >= WHITENING_RATIO_SIGNIFICANT:
        whitening_severity = 1.0
    elif whitening_ratio >= WHITENING_RATIO_MODERATE:
        whitening_severity = 0.6
    elif whitening_ratio >= WHITENING_RATIO_MINOR:
        whitening_severity = 0.3
    else:
        whitening_severity = whitening_ratio / WHITENING_RATIO_MINOR * 0.3
    
    # Combined: take max of whitening and chipping
    severity = max(whitening_severity, chipping_score)
    
    return min(1.0, severity)


def detect_edge_defects(image: Image.Image) -> EdgesResult:
    """Detect edge defects in a canonical card image.
    
    Args:
        image: Canonical RGB image (744x1040)
    
    Returns:
        EdgesResult with severity and per-edge analysis
    """
    rgb = np.array(image.convert("RGB"))
    h, w = rgb.shape[:2]
    
    # Use different band widths for horizontal vs vertical edges
    band_w = int(w * BORDER_BAND_FRACTION)
    band_h = int(h * BORDER_BAND_FRACTION)
    
    edges_config = [
        ("top", band_h),
        ("bottom", band_h),
        ("left", band_w),
        ("right", band_w),
    ]
    
    analyses = []
    
    for edge_name, band_size in edges_config:
        band = _extract_edge_band(rgb, edge_name, band_size)
        
        whitening_ratio, brightness_mean = _analyze_edge_whitening(band)
        brightness_std = _analyze_chipping(band, edge_name)
        chipping_score = _compute_chipping_score(brightness_std)
        severity = _compute_edge_severity(whitening_ratio, chipping_score)
        
        analysis = EdgeAnalysis(
            name=edge_name,
            whitening_ratio=whitening_ratio,
            brightness_mean=brightness_mean,
            brightness_std=brightness_std,
            chipping_score=chipping_score,
            severity=severity,
        )
        analyses.append(analysis)
    
    # Overall severity: max of individual edges
    overall_severity = max(a.severity for a in analyses)
    
    details = {
        "band_sizes": {"horizontal": band_h, "vertical": band_w},
        "thresholds": {
            "whitening_brightness": WHITENING_BRIGHTNESS_THRESHOLD,
            "whitening_ratio_minor": WHITENING_RATIO_MINOR,
            "chipping_std_minor": CHIPPING_STD_THRESHOLD_MINOR,
        },
        "per_edge_summary": {
            a.name: {
                "whitening_ratio": round(a.whitening_ratio, 4),
                "chipping_score": round(a.chipping_score, 4),
                "severity": round(a.severity, 4),
            }
            for a in analyses
        },
    }
    
    return EdgesResult(
        severity=overall_severity,
        per_edge=tuple(analyses),
        details=details,
    )
