from __future__ import annotations

"""PSA centering rules (official PSA grading standards).

Source: https://www.psacard.com/gradingstandards (Card Grading)

Notes:
- PSA uses approximate language for some grades ("approximately").
- PSA explicitly states a centering note: "At the grader's sole discretion, a small variance may be permitted on occasion based on the card’s overall eye appeal."
- PSA does NOT specify a centering ratio for PSA 1 (Poor) on the grading standards page.
  We treat PSA 1 as: centering is non-gating (return None).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CenteringThreshold:
    # expressed as the larger-side percentage (e.g. 55 means 55/45)
    front_max: float
    back_max: float


# Larger-side max percentage (x means x/(100-x)).
# For "or better" thresholds, that means the larger side must be <= x.
PSA_CENTERING_THRESHOLDS: dict[float, CenteringThreshold] = {
    10.0: CenteringThreshold(front_max=55.0, back_max=75.0),
    9.0: CenteringThreshold(front_max=60.0, back_max=90.0),
    8.0: CenteringThreshold(front_max=65.0, back_max=90.0),
    7.0: CenteringThreshold(front_max=70.0, back_max=90.0),
    6.0: CenteringThreshold(front_max=80.0, back_max=90.0),
    5.0: CenteringThreshold(front_max=85.0, back_max=90.0),
    4.0: CenteringThreshold(front_max=85.0, back_max=90.0),
    3.0: CenteringThreshold(front_max=90.0, back_max=90.0),
    2.0: CenteringThreshold(front_max=90.0, back_max=90.0),
    1.5: CenteringThreshold(front_max=90.0, back_max=90.0),
    # PSA 1 is intentionally omitted (no stated centering threshold)
}


def _max_side_ratio(percent_a: float, percent_b: float) -> float:
    """Return the larger-side percent (e.g. 52.1 for 52.1/47.9)."""
    return float(max(percent_a, percent_b))


def centering_passes_for_grade(
    grade: float,
    front_lr: tuple[float, float],
    front_tb: tuple[float, float],
    back_lr: tuple[float, float],
    back_tb: tuple[float, float],
) -> Optional[bool]:
    """Return True/False if centering passes for the given grade.

    Returns None for PSA 1 (no stated centering threshold).

    The "front" threshold is evaluated using the *worst* of LR/TB.
    The "back" threshold is evaluated using the *worst* of LR/TB.

    Args:
      grade: PSA grade (10..1.5); PSA 1 returns None.
      front_lr: (left%, right%)
      front_tb: (top%, bottom%)
      back_lr: (left%, right%)
      back_tb: (top%, bottom%)
    """
    if float(grade) == 1.0:
        return None

    thr = PSA_CENTERING_THRESHOLDS.get(float(grade))
    if thr is None:
        raise KeyError(f"No centering threshold configured for grade={grade}")

    front_worst = max(_max_side_ratio(*front_lr), _max_side_ratio(*front_tb))
    back_worst = max(_max_side_ratio(*back_lr), _max_side_ratio(*back_tb))

    return (front_worst <= thr.front_max) and (back_worst <= thr.back_max)


def psa_max_grade_by_centering(
    front_lr: tuple[float, float],
    front_tb: tuple[float, float],
    back_lr: tuple[float, float],
    back_tb: tuple[float, float],
) -> float:
    """Return the maximum PSA grade allowed by centering alone.

    We iterate from 10 → 1.5 and return the first grade whose threshold passes.
    If nothing passes, we return 1.0.

    PSA 1 does not have a published centering threshold, so it's the fallback.
    """
    for g in [10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.5]:
        ok = centering_passes_for_grade(g, front_lr, front_tb, back_lr, back_tb)
        if ok is True:
            return g

    return 1.0
