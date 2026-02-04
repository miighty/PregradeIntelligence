from __future__ import annotations

"""Surface defect detection.

Detects scratches, scuffs, and print lines on card surface using deterministic
heuristics on canonical images.

Approach:
1. Work on the interior region (excluding borders already analyzed).
2. Use gradient/line detection to identify linear artifacts (scratches, print lines).
3. Use texture variance to flag scuffs (local irregularities).
4. Return severity scores [0..1] and evidence for explainability.

All thresholds are fixed constants for determinism and explainability.
"""

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
from PIL import Image

try:
    import cv2
except ImportError as e:
    raise ImportError(
        "opencv-python is required for surface detection. "
        "Install with: pip install opencv-python"
    ) from e


# Interior region: exclude this fraction from each edge
INTERIOR_MARGIN_FRACTION = 0.05

# Scratch detection thresholds (normal cards)
SCRATCH_LINE_MIN_LENGTH = 30  # Minimum length in pixels
SCRATCH_LINE_MIN_LENGTH_TEXTURED = 80  # Longer minimum for textured/holographic cards
SCRATCH_LINE_THRESHOLD = 50  # Canny threshold for line detection
SCRATCH_COUNT_MINOR = 2  # Number of detected lines
SCRATCH_COUNT_MODERATE = 5
SCRATCH_COUNT_SIGNIFICANT = 10

# Texture detection thresholds (for holographic/special cards)
TEXTURE_EDGE_DENSITY_THRESHOLD = 0.10  # >10% edge pixels = textured card
TEXTURE_MAX_SCRATCH_COUNT = 15  # If >=15 lines detected on textured card, assume pattern not scratches
SCRATCH_CONTRAST_THRESHOLD = 30.0  # Min brightness difference for real scratch (higher = stricter)

# Scuff detection: local texture variance
SCUFF_VARIANCE_THRESHOLD_MINOR = 15.0
SCUFF_VARIANCE_THRESHOLD_MODERATE = 25.0
SCUFF_VARIANCE_THRESHOLD_SIGNIFICANT = 40.0
# Higher baseline for textured cards (holographic patterns have high variance)
# Holographic cards can have texture variance of 1000-2000+ which is normal
SCUFF_VARIANCE_BASELINE_TEXTURED = 1500.0  # Texture variance above this is abnormal for holo

# Print line detection (regular vertical/horizontal artifacts)
PRINT_LINE_REGULARITY_THRESHOLD = 0.7  # High regularity = print defect


@dataclass(frozen=True)
class ScratchInfo:
    """Information about a detected scratch."""
    x1: int
    y1: int
    x2: int
    y2: int
    length: float


@dataclass(frozen=True)
class SurfaceResult:
    """Complete surface analysis result."""
    severity: float
    scratch_count: int
    scratch_severity: float
    scuff_severity: float
    texture_variance: float
    scratches: tuple[ScratchInfo, ...]
    details: dict[str, Any]


def _extract_interior(img: np.ndarray) -> np.ndarray:
    """Extract the interior region, excluding borders."""
    h, w = img.shape[:2]
    margin_x = int(w * INTERIOR_MARGIN_FRACTION)
    margin_y = int(h * INTERIOR_MARGIN_FRACTION)
    
    return img[margin_y:h - margin_y, margin_x:w - margin_x]


def _is_textured_surface(gray: np.ndarray) -> tuple[bool, float]:
    """Detect if surface has high baseline texture (holographic/special cards).
    
    Holographic and special illustration rare cards have complex patterns that
    create many edges. This function detects such cards by measuring edge density.
    
    Returns:
        (is_textured, edge_density) where edge_density is fraction of edge pixels
    """
    edges = cv2.Canny(gray, SCRATCH_LINE_THRESHOLD, SCRATCH_LINE_THRESHOLD * 2)
    edge_density = float(np.sum(edges > 0)) / float(edges.size)
    is_textured = edge_density > TEXTURE_EDGE_DENSITY_THRESHOLD
    return is_textured, edge_density


def _compute_line_contrast(gray: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> float:
    """Compute the contrast of a line against its local neighborhood.
    
    Real scratches typically have different brightness than their surroundings.
    Pattern edges from holographic cards blend with surroundings.
    
    Returns:
        Absolute brightness difference between line pixels and neighboring pixels
    """
    h, w = gray.shape
    
    # Sample points along the line
    num_samples = min(10, max(3, int(np.sqrt((x2 - x1)**2 + (y2 - y1)**2) / 10)))
    
    line_values = []
    neighbor_values = []
    
    for i in range(num_samples):
        t = i / max(1, num_samples - 1)
        px = int(x1 + t * (x2 - x1))
        py = int(y1 + t * (y2 - y1))
        
        if 0 <= px < w and 0 <= py < h:
            line_values.append(float(gray[py, px]))
            
            # Sample perpendicular neighbors (offset by ~5 pixels)
            dx = x2 - x1
            dy = y2 - y1
            length = max(1, np.sqrt(dx**2 + dy**2))
            # Perpendicular direction
            perp_x = -dy / length
            perp_y = dx / length
            
            for offset in [-5, 5]:
                nx = int(px + offset * perp_x)
                ny = int(py + offset * perp_y)
                if 0 <= nx < w and 0 <= ny < h:
                    neighbor_values.append(float(gray[ny, nx]))
    
    if not line_values or not neighbor_values:
        return 0.0
    
    line_mean = np.mean(line_values)
    neighbor_mean = np.mean(neighbor_values)
    
    return abs(line_mean - neighbor_mean)


def _detect_scratches(gray: np.ndarray, is_textured: bool = False) -> list[ScratchInfo]:
    """Detect linear scratches using Hough line detection.
    
    For textured/holographic cards, uses stricter criteria to avoid false positives
    from pattern edges.
    
    Args:
        gray: Grayscale image of interior region
        is_textured: Whether this is a textured/holographic card
    
    Returns:
        List of detected scratches
    """
    # Use longer minimum length for textured cards
    min_length = SCRATCH_LINE_MIN_LENGTH_TEXTURED if is_textured else SCRATCH_LINE_MIN_LENGTH
    
    # Edge detection
    edges = cv2.Canny(gray, SCRATCH_LINE_THRESHOLD, SCRATCH_LINE_THRESHOLD * 2)
    
    # Probabilistic Hough transform
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=50,
        minLineLength=min_length,
        maxLineGap=10,
    )
    
    if lines is None:
        return []
    
    scratches = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        length = float(np.sqrt((x2 - x1)**2 + (y2 - y1)**2))
        
        # Filter: scratches are typically not perfectly horizontal or vertical
        # (those are more likely print artifacts or card features)
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        if length > 0:
            angle_ratio = min(dx, dy) / length
            # Accept lines that are at least somewhat diagonal
            if angle_ratio > 0.1 or length > min_length * 2:
                # For textured cards, also check contrast
                if is_textured:
                    contrast = _compute_line_contrast(gray, int(x1), int(y1), int(x2), int(y2))
                    if contrast < SCRATCH_CONTRAST_THRESHOLD:
                        # Low contrast = probably pattern edge, not scratch
                        continue
                
                scratches.append(ScratchInfo(
                    x1=int(x1), y1=int(y1),
                    x2=int(x2), y2=int(y2),
                    length=length,
                ))
    
    # For textured cards, if we still detect too many lines, assume they're pattern
    if is_textured and len(scratches) >= TEXTURE_MAX_SCRATCH_COUNT:
        # Return empty - this many "scratches" is clearly pattern, not defects
        return []
    
    return scratches


def _compute_scratch_severity(scratch_count: int, is_textured: bool = False) -> float:
    """Convert scratch count to severity score.
    
    For textured cards, uses higher thresholds since some pattern edges may
    pass contrast checks.
    """
    if is_textured:
        # Textured cards: use 2x thresholds for severity
        minor = SCRATCH_COUNT_MINOR * 2
        moderate = SCRATCH_COUNT_MODERATE * 2
        significant = SCRATCH_COUNT_SIGNIFICANT * 2
    else:
        minor = SCRATCH_COUNT_MINOR
        moderate = SCRATCH_COUNT_MODERATE
        significant = SCRATCH_COUNT_SIGNIFICANT
    
    if scratch_count >= significant:
        return 1.0
    elif scratch_count >= moderate:
        return 0.6
    elif scratch_count >= minor:
        return 0.3
    elif scratch_count > 0:
        return scratch_count / minor * 0.3
    return 0.0


def _analyze_texture_variance(gray: np.ndarray) -> float:
    """Analyze local texture variance to detect scuffs.
    
    Scuffs appear as regions of irregular texture compared to surrounding area.
    """
    # Divide into blocks and compute local variance
    block_size = 32
    h, w = gray.shape
    
    if h < block_size or w < block_size:
        return float(np.std(gray))
    
    variances = []
    for y in range(0, h - block_size, block_size):
        for x in range(0, w - block_size, block_size):
            block = gray[y:y + block_size, x:x + block_size]
            variances.append(np.var(block))
    
    if not variances:
        return 0.0
    
    # High variance of variances indicates uneven texture (scuffs)
    return float(np.std(variances))


def _compute_scuff_severity(texture_variance: float) -> float:
    """Convert texture variance to scuff severity."""
    if texture_variance >= SCUFF_VARIANCE_THRESHOLD_SIGNIFICANT:
        return 1.0
    elif texture_variance >= SCUFF_VARIANCE_THRESHOLD_MODERATE:
        return 0.6
    elif texture_variance >= SCUFF_VARIANCE_THRESHOLD_MINOR:
        return 0.3
    else:
        return texture_variance / SCUFF_VARIANCE_THRESHOLD_MINOR * 0.3


def _compute_scuff_severity_textured(texture_variance: float) -> float:
    """Compute scuff severity for textured/holographic cards.
    
    Textured cards have inherently high texture variance from their patterns,
    so we use a higher baseline and only flag truly abnormal variance.
    """
    # Subtract baseline for textured cards
    adjusted_variance = max(0.0, texture_variance - SCUFF_VARIANCE_BASELINE_TEXTURED)
    
    # Scale the adjusted variance
    scaled = adjusted_variance / 200.0  # Scale factor for textured cards
    
    if scaled >= 1.0:
        return 1.0
    elif scaled >= 0.5:
        return 0.6
    elif scaled >= 0.2:
        return 0.3
    else:
        return scaled * 0.3 / 0.2


def detect_surface_defects(image: Image.Image) -> SurfaceResult:
    """Detect surface defects in a canonical card image.
    
    Handles both normal cards and textured/holographic cards by detecting
    high-texture surfaces and adjusting detection criteria accordingly.
    
    Args:
        image: Canonical RGB image (744x1040)
    
    Returns:
        SurfaceResult with severity and defect details
    """
    rgb = np.array(image.convert("RGB"))
    interior = _extract_interior(rgb)
    
    # Convert to grayscale for analysis
    gray = cv2.cvtColor(interior, cv2.COLOR_RGB2GRAY)
    
    # Detect if this is a textured/holographic card
    is_textured, edge_density = _is_textured_surface(gray)
    
    # Detect scratches (with texture-aware filtering)
    scratches = _detect_scratches(gray, is_textured=is_textured)
    scratch_count = len(scratches)
    scratch_severity = _compute_scratch_severity(scratch_count, is_textured=is_textured)
    
    # Analyze texture for scuffs
    texture_variance = _analyze_texture_variance(gray)
    
    # Use different scuff severity calculation for textured cards
    if is_textured:
        scuff_severity = _compute_scuff_severity_textured(texture_variance)
    else:
        scuff_severity = _compute_scuff_severity(texture_variance)
    
    # Combined severity: max of scratch and scuff severity
    overall_severity = max(scratch_severity, scuff_severity)
    
    details = {
        "interior_size": gray.shape,
        "is_textured": is_textured,
        "edge_density": round(edge_density, 4),
        "scratch_count": scratch_count,
        "texture_variance": round(texture_variance, 4),
        "thresholds": {
            "scratch_min_length": SCRATCH_LINE_MIN_LENGTH_TEXTURED if is_textured else SCRATCH_LINE_MIN_LENGTH,
            "scratch_count_minor": SCRATCH_COUNT_MINOR,
            "scuff_variance_minor": SCUFF_VARIANCE_THRESHOLD_MINOR,
            "texture_edge_density_threshold": TEXTURE_EDGE_DENSITY_THRESHOLD,
        },
        "scratch_locations": [
            {"x1": s.x1, "y1": s.y1, "x2": s.x2, "y2": s.y2, "length": round(s.length, 1)}
            for s in scratches[:10]  # Limit to first 10 for response size
        ],
    }
    
    return SurfaceResult(
        severity=overall_severity,
        scratch_count=scratch_count,
        scratch_severity=scratch_severity,
        scuff_severity=scuff_severity,
        texture_variance=texture_variance,
        scratches=tuple(scratches),
        details=details,
    )
