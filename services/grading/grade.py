from __future__ import annotations

"""Grade inference (v0).

This is intentionally heuristic-only until we have a labelled PSA dataset.
Outputs are meant to be explainable and stable, not "accurate" yet.

Primary output: P(PSA10).
Secondary output: distribution over {7,8,9,10}.
"""

from dataclasses import dataclass
from typing import Any

from PIL import Image

from services.grading.canonical import canonicalize
from services.grading.centering import measure_centering, render_centering_overlay
from services.grading.types import (
    GradeDistribution,
    CenteringResult,
    DefectSignals,
    PhotoQuality,
    GradeResult,
)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _softmax4(logits: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    import math

    m = max(logits)
    exps = [math.exp(l - m) for l in logits]
    s = sum(exps)
    return tuple(e / s for e in exps)  # type: ignore


def grade_card(front: Image.Image, back: Image.Image) -> GradeResult:
    # Canonicalize
    cf = canonicalize(front)
    cb = canonicalize(back)

    # Centering
    cent = measure_centering(cf.image, cb.image)

    # v0 defects (placeholder): until implemented, assume neutral but reflect uncertainty
    defects = DefectSignals(
        corners_severity=0.2,
        edges_severity=0.2,
        surface_severity=0.2,
        details={"note": "v0 placeholder; defect detectors not implemented yet"},
    )

    # v0 photo quality (placeholder)
    pq = PhotoQuality(
        blur=0.0,
        glare=0.0,
        occlusion=0.0,
        usable=True,
        reasons=(),
    )

    # Convert centering max to a centering score (very rough)
    # 10 -> 1.0, 9 -> 0.85, 8 -> 0.7, 7 -> 0.55, else lower.
    cent_score_map = {10.0: 1.0, 9.0: 0.85, 8.0: 0.7, 7.0: 0.55, 6.0: 0.4, 5.0: 0.3, 4.0: 0.25, 3.0: 0.2, 2.0: 0.15, 1.5: 0.12, 1.0: 0.1}
    cent_score = float(cent_score_map.get(cent.psa_max, 0.1))

    # v0 p10: centering is a hard ceiling; defects reduce.
    defect_penalty = (defects.corners_severity + defects.edges_severity + defects.surface_severity) / 3.0
    p10 = _clamp01(0.05 + 0.9 * cent_score - 0.6 * defect_penalty)

    # v0 distribution logits
    # If p10 high, shift mass to 10/9, else to 8/7.
    l10 = 2.0 * p10
    l9 = 1.2 * (0.9 - defect_penalty) + 0.2 * cent_score
    l8 = 1.0 - 0.6 * cent_score
    l7 = 0.7 + 0.2 * defect_penalty
    p7, p8, p9, p10_dist = _softmax4((l7, l8, l9, l10))

    expected = 7.0 * p7 + 8.0 * p8 + 9.0 * p9 + 10.0 * p10_dist

    confidence = _clamp01(0.3 + 0.4 * cent_score + 0.3 * (1.0 - defect_penalty))

    # Explanations: centering overlays
    front_overlay = render_centering_overlay(
        cf.image,
        cent.details.get("front_inner_rect"),
        cent.front_lr,
        cent.front_tb,
        title="Front centering",
    )
    back_overlay = render_centering_overlay(
        cb.image,
        cent.details.get("back_inner_rect"),
        cent.back_lr,
        cent.back_tb,
        title=f"Back centering ({cent.details.get('back_method')})",
        pokeball=cent.details.get("back_pokeball"),
    )

    # We return images in-memory; API layer decides storage/encoding.
    explanations: dict[str, Any] = {
        "centering": {
            "front_overlay_image": front_overlay,
            "back_overlay_image": back_overlay,
        }
    }

    trace: dict[str, Any] = {
        "canonical": {
            "front": {"warp_used": cf.warp_used, "warp_reason": cf.warp_reason, "warp_debug": cf.warp_debug},
            "back": {"warp_used": cb.warp_used, "warp_reason": cb.warp_reason, "warp_debug": cb.warp_debug},
        },
        "centering": cent.details,
    }

    return GradeResult(
        grade_distribution=GradeDistribution(p7=p7, p8=p8, p9=p9, p10=p10_dist),
        expected_grade=expected,
        p_psa10=p10,
        confidence=confidence,
        centering=CenteringResult(
            lr_ratio=max(cent.front_lr),
            tb_ratio=max(cent.front_tb),
            psa_max=int(cent.psa_max) if cent.psa_max != 1.5 else 1,
            score=cent_score,
            details=cent.details,
        ),
        defects=defects,
        photo_quality=pq,
        explanations=explanations,
        trace=trace,
    )
