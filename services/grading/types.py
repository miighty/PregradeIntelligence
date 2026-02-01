from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class GradeDistribution:
    p7: float
    p8: float
    p9: float
    p10: float

    def to_dict(self) -> dict[str, float]:
        return {
            "7": float(self.p7),
            "8": float(self.p8),
            "9": float(self.p9),
            "10": float(self.p10),
        }


@dataclass(frozen=True)
class CenteringResult:
    lr_ratio: float  # e.g. 52.1 means 52.1/47.9
    tb_ratio: float
    psa_max: int
    score: float  # 0..1
    details: dict[str, Any]


@dataclass(frozen=True)
class DefectSignals:
    corners_severity: float
    edges_severity: float
    surface_severity: float
    details: dict[str, Any]


@dataclass(frozen=True)
class PhotoQuality:
    blur: float
    glare: float
    occlusion: float
    usable: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class GradeResult:
    grade_distribution: GradeDistribution
    expected_grade: float
    p_psa10: float
    confidence: float
    centering: CenteringResult
    defects: DefectSignals
    photo_quality: PhotoQuality
    explanations: dict[str, Any]
    trace: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "grade_distribution": self.grade_distribution.to_dict(),
            "expected_grade": float(self.expected_grade),
            "p_psa10": float(self.p_psa10),
            "confidence": float(self.confidence),
            "centering": {
                "lr_ratio": float(self.centering.lr_ratio),
                "tb_ratio": float(self.centering.tb_ratio),
                "psa_max": int(self.centering.psa_max),
                "score": float(self.centering.score),
                "details": self.centering.details,
            },
            "defects": {
                "corners": {"severity": float(self.defects.corners_severity)},
                "edges": {"severity": float(self.defects.edges_severity)},
                "surface": {"severity": float(self.defects.surface_severity)},
                "details": self.defects.details,
            },
            "photo_quality": {
                "blur": float(self.photo_quality.blur),
                "glare": float(self.photo_quality.glare),
                "occlusion": float(self.photo_quality.occlusion),
                "usable": bool(self.photo_quality.usable),
                "reasons": list(self.photo_quality.reasons),
            },
            "explanations": self.explanations,
            "trace": self.trace,
        }
