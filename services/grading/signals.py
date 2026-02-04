from __future__ import annotations

"""ConditionSignal generation from grading results.

Converts raw detector outputs into human-readable ConditionSignal objects
suitable for the API response.

All severity mappings use fixed thresholds for determinism and explainability.
"""

from domain.types import ConditionSignal
from services.grading.types import GradeResult, DefectSignals, PhotoQuality, CenteringResult


# Severity thresholds (severity score 0..1 -> severity label)
SEVERITY_MINOR = 0.25
SEVERITY_MODERATE = 0.50
SEVERITY_SIGNIFICANT = 0.75


def _severity_label(score: float) -> str:
    """Convert a 0..1 severity score to a severity label."""
    if score >= SEVERITY_SIGNIFICANT:
        return "significant"
    elif score >= SEVERITY_MODERATE:
        return "moderate"
    elif score >= SEVERITY_MINOR:
        return "minor"
    return "none"


def _centering_confidence(centering: CenteringResult) -> float:
    """Compute confidence for centering signal based on detection success."""
    details = centering.details
    front_detected = details.get("front_detected", False)
    back_detected = details.get("back_detected", False)
    
    if front_detected and back_detected:
        return 0.90
    elif front_detected or back_detected:
        return 0.70
    return 0.40


def _centering_observation(centering: CenteringResult) -> str:
    """Generate human-readable observation for centering."""
    lr = centering.lr_ratio
    tb = centering.tb_ratio
    psa_max = centering.psa_max
    
    if psa_max >= 10:
        return f"Centering is excellent (LR {lr:.1f}%, TB {tb:.1f}%), consistent with PSA 10 standards"
    elif psa_max >= 9:
        return f"Centering shows slight variance (LR {lr:.1f}%, TB {tb:.1f}%), consistent with PSA 9 standards"
    elif psa_max >= 8:
        return f"Centering shows noticeable variance (LR {lr:.1f}%, TB {tb:.1f}%), may limit to PSA 8"
    elif psa_max >= 7:
        return f"Centering is off-center (LR {lr:.1f}%, TB {tb:.1f}%), likely limited to PSA 7"
    else:
        return f"Centering is significantly off-center (LR {lr:.1f}%, TB {tb:.1f}%), below PSA 7 threshold"


def _centering_evidence(centering: CenteringResult) -> str:
    """Generate evidence description for centering."""
    lr = centering.lr_ratio
    tb = centering.tb_ratio
    details = centering.details
    
    method = details.get("back_method", "unknown")
    return f"Left-right ratio {lr:.1f}%, top-bottom ratio {tb:.1f}%. Back measured via {method}."


def _centering_severity(centering: CenteringResult) -> str:
    """Map centering PSA max to severity label."""
    psa_max = centering.psa_max
    if psa_max >= 9:
        return "none"
    elif psa_max >= 8:
        return "minor"
    elif psa_max >= 7:
        return "moderate"
    return "significant"


def _corners_observation(defects: DefectSignals) -> str:
    """Generate human-readable observation for corners."""
    severity = defects.corners_severity
    details = defects.details.get("corners", {})
    summary = details.get("per_corner_summary", {})
    
    # Find the worst corner
    worst_corner = None
    worst_severity = 0.0
    for corner, data in summary.items():
        if data.get("severity", 0) > worst_severity:
            worst_severity = data.get("severity", 0)
            worst_corner = corner.replace("_", " ")
    
    if severity < SEVERITY_MINOR:
        return "All corners show minimal wear, consistent with pack-fresh condition"
    elif severity < SEVERITY_MODERATE:
        return f"Minor wear detected, most noticeable at {worst_corner or 'corners'}"
    elif severity < SEVERITY_SIGNIFICANT:
        return f"Moderate corner wear detected at {worst_corner or 'multiple corners'}, showing whitening"
    else:
        return f"Significant corner damage at {worst_corner or 'multiple corners'}, notable whitening or flattening"


def _corners_evidence(defects: DefectSignals) -> str:
    """Generate evidence description for corners."""
    details = defects.details.get("corners", {})
    summary = details.get("per_corner_summary", {})
    
    parts = []
    for corner, data in summary.items():
        whitening = data.get("whitening_ratio", 0) * 100
        if whitening > 5:
            parts.append(f"{corner.replace('_', ' ')}: {whitening:.1f}% whitening")
    
    if parts:
        return "; ".join(parts)
    return "Corner analysis shows no significant whitening detected"


def _edges_observation(defects: DefectSignals) -> str:
    """Generate human-readable observation for edges."""
    severity = defects.edges_severity
    details = defects.details.get("edges", {})
    summary = details.get("per_edge_summary", {})
    
    # Find the worst edge
    worst_edge = None
    worst_severity = 0.0
    for edge, data in summary.items():
        if data.get("severity", 0) > worst_severity:
            worst_severity = data.get("severity", 0)
            worst_edge = edge
    
    if severity < SEVERITY_MINOR:
        return "Edges show minimal wear, no visible chipping or whitening"
    elif severity < SEVERITY_MODERATE:
        return f"Minor edge wear detected, most noticeable along {worst_edge or 'edges'}"
    elif severity < SEVERITY_SIGNIFICANT:
        return f"Moderate edge wear along {worst_edge or 'multiple edges'}, some whitening visible"
    else:
        return f"Significant edge damage along {worst_edge or 'multiple edges'}, visible chipping or whitening"


def _edges_evidence(defects: DefectSignals) -> str:
    """Generate evidence description for edges."""
    details = defects.details.get("edges", {})
    summary = details.get("per_edge_summary", {})
    
    parts = []
    for edge, data in summary.items():
        whitening = data.get("whitening_ratio", 0) * 100
        chipping = data.get("chipping_score", 0) * 100
        if whitening > 5 or chipping > 20:
            parts.append(f"{edge}: whitening {whitening:.1f}%, chipping {chipping:.0f}%")
    
    if parts:
        return "; ".join(parts)
    return "Edge analysis shows consistent color along all borders"


def _surface_observation(defects: DefectSignals) -> str:
    """Generate human-readable observation for surface."""
    severity = defects.surface_severity
    details = defects.details.get("surface", {})
    scratch_count = details.get("scratch_count", 0)
    
    if severity < SEVERITY_MINOR:
        return "Surface is clean with no visible scratches or scuffs"
    elif severity < SEVERITY_MODERATE:
        if scratch_count > 0:
            return f"Surface shows {scratch_count} minor scratches visible under analysis"
        return "Surface shows minor texture irregularities"
    elif severity < SEVERITY_SIGNIFICANT:
        if scratch_count > 0:
            return f"Surface has {scratch_count} scratches, some may be visible to naked eye"
        return "Surface shows moderate wear and texture irregularities"
    else:
        if scratch_count > 0:
            return f"Surface has {scratch_count} notable scratches and visible wear"
        return "Surface shows significant wear, scuffs, or damage"


def _surface_evidence(defects: DefectSignals) -> str:
    """Generate evidence description for surface."""
    details = defects.details.get("surface", {})
    scratch_count = details.get("scratch_count", 0)
    texture_var = details.get("texture_variance", 0)
    
    parts = []
    if scratch_count > 0:
        parts.append(f"{scratch_count} linear artifacts detected")
    parts.append(f"texture variance {texture_var:.1f}")
    
    return "; ".join(parts)


def generate_condition_signals(result: GradeResult) -> tuple[ConditionSignal, ...]:
    """Generate ConditionSignal objects from a GradeResult.
    
    Args:
        result: The complete grading result with centering, defects, and photo quality
    
    Returns:
        Tuple of ConditionSignal objects for inclusion in API response
    """
    signals = []
    
    # Centering signal
    signals.append(ConditionSignal(
        signal_type="centering",
        observation=_centering_observation(result.centering),
        severity=_centering_severity(result.centering),
        confidence=_centering_confidence(result.centering),
        evidence_description=_centering_evidence(result.centering),
    ))
    
    # Corners signal
    signals.append(ConditionSignal(
        signal_type="corners",
        observation=_corners_observation(result.defects),
        severity=_severity_label(result.defects.corners_severity),
        confidence=0.85,  # Fixed confidence for heuristic detectors
        evidence_description=_corners_evidence(result.defects),
    ))
    
    # Edges signal
    signals.append(ConditionSignal(
        signal_type="edges",
        observation=_edges_observation(result.defects),
        severity=_severity_label(result.defects.edges_severity),
        confidence=0.85,
        evidence_description=_edges_evidence(result.defects),
    ))
    
    # Surface signal
    signals.append(ConditionSignal(
        signal_type="surface",
        observation=_surface_observation(result.defects),
        severity=_severity_label(result.defects.surface_severity),
        confidence=0.80,  # Slightly lower confidence for surface detection
        evidence_description=_surface_evidence(result.defects),
    ))
    
    return tuple(signals)
