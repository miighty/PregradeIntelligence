from __future__ import annotations

"""Photo quality detection.

Detects blur, glare, and occlusion in card images using deterministic
heuristics.

Approach:
1. Blur: Variance of Laplacian (low variance = blurry).
2. Glare: Percentage of saturated bright pixels.
3. Occlusion: Large dark/unexpected regions in expected card area.
4. Return quality scores and usability flag with explicit reasons.

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
        "opencv-python is required for photo quality detection. "
        "Install with: pip install opencv-python"
    ) from e


# Blur detection thresholds (variance of Laplacian)
BLUR_VARIANCE_USABLE = 100.0  # Below this = too blurry to use
BLUR_VARIANCE_GOOD = 300.0  # Above this = good quality
BLUR_VARIANCE_EXCELLENT = 500.0

# Glare detection thresholds
GLARE_SATURATION_THRESHOLD = 250  # Pixels above this are glare
GLARE_RATIO_MINOR = 0.02  # 2% glare = minor
GLARE_RATIO_MODERATE = 0.08  # 8% = moderate (may affect analysis)
GLARE_RATIO_UNUSABLE = 0.15  # 15% = too much glare

# Occlusion detection thresholds
OCCLUSION_DARK_THRESHOLD = 30  # Pixels below this are "occluded"
OCCLUSION_RATIO_MINOR = 0.05  # 5% dark = minor
OCCLUSION_RATIO_MODERATE = 0.15  # 15% = moderate
OCCLUSION_RATIO_UNUSABLE = 0.25  # 25% = too much occlusion


@dataclass(frozen=True)
class PhotoQualityResult:
    """Complete photo quality analysis result."""
    blur: float  # 0..1, higher = worse (more blurry)
    glare: float  # 0..1, higher = worse (more glare)
    occlusion: float  # 0..1, higher = worse (more occluded)
    usable: bool
    reasons: tuple[str, ...]
    details: dict[str, Any]


def _measure_blur(gray: np.ndarray) -> tuple[float, float]:
    """Measure blur using variance of Laplacian.
    
    Returns:
        (blur_score 0..1, laplacian_variance)
    """
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    variance = float(np.var(laplacian))
    
    # Convert to 0..1 score where higher = worse (more blurry)
    if variance >= BLUR_VARIANCE_EXCELLENT:
        blur_score = 0.0
    elif variance >= BLUR_VARIANCE_GOOD:
        blur_score = 0.1
    elif variance >= BLUR_VARIANCE_USABLE:
        # Linear interpolation
        blur_score = 0.1 + 0.4 * (BLUR_VARIANCE_GOOD - variance) / (BLUR_VARIANCE_GOOD - BLUR_VARIANCE_USABLE)
    else:
        # Very blurry
        blur_score = 0.5 + 0.5 * (BLUR_VARIANCE_USABLE - variance) / BLUR_VARIANCE_USABLE
        blur_score = min(1.0, blur_score)
    
    return blur_score, variance


def _measure_glare(gray: np.ndarray) -> tuple[float, float]:
    """Measure glare by counting saturated bright pixels.
    
    Returns:
        (glare_score 0..1, glare_ratio)
    """
    total_pixels = gray.size
    glare_pixels = np.sum(gray > GLARE_SATURATION_THRESHOLD)
    glare_ratio = float(glare_pixels) / float(total_pixels) if total_pixels > 0 else 0.0
    
    # Convert to 0..1 score
    if glare_ratio >= GLARE_RATIO_UNUSABLE:
        glare_score = 1.0
    elif glare_ratio >= GLARE_RATIO_MODERATE:
        glare_score = 0.5 + 0.5 * (glare_ratio - GLARE_RATIO_MODERATE) / (GLARE_RATIO_UNUSABLE - GLARE_RATIO_MODERATE)
    elif glare_ratio >= GLARE_RATIO_MINOR:
        glare_score = 0.2 + 0.3 * (glare_ratio - GLARE_RATIO_MINOR) / (GLARE_RATIO_MODERATE - GLARE_RATIO_MINOR)
    else:
        glare_score = glare_ratio / GLARE_RATIO_MINOR * 0.2
    
    return glare_score, glare_ratio


def _measure_occlusion(gray: np.ndarray) -> tuple[float, float]:
    """Measure occlusion by detecting large dark regions.
    
    Returns:
        (occlusion_score 0..1, dark_ratio)
    """
    total_pixels = gray.size
    dark_pixels = np.sum(gray < OCCLUSION_DARK_THRESHOLD)
    dark_ratio = float(dark_pixels) / float(total_pixels) if total_pixels > 0 else 0.0
    
    # Convert to 0..1 score
    if dark_ratio >= OCCLUSION_RATIO_UNUSABLE:
        occlusion_score = 1.0
    elif dark_ratio >= OCCLUSION_RATIO_MODERATE:
        occlusion_score = 0.5 + 0.5 * (dark_ratio - OCCLUSION_RATIO_MODERATE) / (OCCLUSION_RATIO_UNUSABLE - OCCLUSION_RATIO_MODERATE)
    elif dark_ratio >= OCCLUSION_RATIO_MINOR:
        occlusion_score = 0.2 + 0.3 * (dark_ratio - OCCLUSION_RATIO_MINOR) / (OCCLUSION_RATIO_MODERATE - OCCLUSION_RATIO_MINOR)
    else:
        occlusion_score = dark_ratio / OCCLUSION_RATIO_MINOR * 0.2
    
    return occlusion_score, dark_ratio


def detect_photo_quality(image: Image.Image) -> PhotoQualityResult:
    """Detect photo quality issues in a card image.
    
    Args:
        image: RGB image (typically canonical 744x1040, but works on any size)
    
    Returns:
        PhotoQualityResult with quality scores and usability flag
    """
    rgb = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    
    # Measure each quality dimension
    blur_score, laplacian_variance = _measure_blur(gray)
    glare_score, glare_ratio = _measure_glare(gray)
    occlusion_score, dark_ratio = _measure_occlusion(gray)
    
    # Determine usability and collect reasons
    reasons = []
    usable = True
    
    if laplacian_variance < BLUR_VARIANCE_USABLE:
        usable = False
        reasons.append(f"Image too blurry (variance {laplacian_variance:.1f} < {BLUR_VARIANCE_USABLE})")
    elif blur_score > 0.3:
        reasons.append(f"Image has noticeable blur (variance {laplacian_variance:.1f})")
    
    if glare_ratio >= GLARE_RATIO_UNUSABLE:
        usable = False
        reasons.append(f"Excessive glare ({glare_ratio * 100:.1f}% saturated pixels)")
    elif glare_ratio >= GLARE_RATIO_MODERATE:
        reasons.append(f"Moderate glare detected ({glare_ratio * 100:.1f}% saturated pixels)")
    
    if dark_ratio >= OCCLUSION_RATIO_UNUSABLE:
        usable = False
        reasons.append(f"Significant occlusion ({dark_ratio * 100:.1f}% dark pixels)")
    elif dark_ratio >= OCCLUSION_RATIO_MODERATE:
        reasons.append(f"Partial occlusion detected ({dark_ratio * 100:.1f}% dark pixels)")
    
    details = {
        "image_size": gray.shape,
        "blur": {
            "laplacian_variance": round(laplacian_variance, 2),
            "score": round(blur_score, 4),
        },
        "glare": {
            "saturated_ratio": round(glare_ratio, 4),
            "score": round(glare_score, 4),
        },
        "occlusion": {
            "dark_ratio": round(dark_ratio, 4),
            "score": round(occlusion_score, 4),
        },
        "thresholds": {
            "blur_usable": BLUR_VARIANCE_USABLE,
            "glare_unusable": GLARE_RATIO_UNUSABLE,
            "occlusion_unusable": OCCLUSION_RATIO_UNUSABLE,
        },
    }
    
    return PhotoQualityResult(
        blur=blur_score,
        glare=glare_score,
        occlusion=occlusion_score,
        usable=usable,
        reasons=tuple(reasons),
        details=details,
    )
