from __future__ import annotations

"""WOTC number fallback helpers.

Goal: pull NN/NN from bottom-right even when generic OCR/template fails.
Works best on warped (canonical) fronts.
"""

import math
import re
from typing import Any, Optional, Tuple

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract

CARD_NUMBER_PATTERN = re.compile(r"(\d{1,3})\s*/\s*(\d{1,3})")


def wotc_number_fallback(front_warped: Image.Image) -> tuple[Optional[str], dict[str, Any]]:
    img = front_warped.convert("RGB")
    W, H = img.size

    # Start from a bottom-right band and then tighten to avoid copyright/year line.
    base = img.crop((int(W * 0.55), int(H * 0.82), W, H))

    # Try multiple subcrops emphasizing the very bottom-right corner.
    candidates: list[tuple[str, Image.Image]] = []
    for (x0, y0) in [(0.20, 0.15), (0.30, 0.25), (0.35, 0.30)]:
        c = base.crop((int(base.size[0] * x0), int(base.size[1] * y0), base.size[0], base.size[1]))
        candidates.append((f"sub_{x0}_{y0}", c))

    angles = [-12, -9, -6, -3, 0, 3, 6, 9, 12]
    psm_modes = [7, 8, 13]

    best_num: Optional[str] = None
    best_score = -1e9
    best_meta: dict[str, Any] = {}

    for label, crop in candidates:
        for ang in angles:
            rot = crop.rotate(ang, expand=True, fillcolor=(255, 255, 255))

            # preprocess: grayscale, upscale, contrast, sharpen
            g = rot.convert("L")
            g = g.resize((g.size[0] * 8, g.size[1] * 8))
            g = ImageEnhance.Contrast(g).enhance(2.5)
            g = g.filter(ImageFilter.SHARPEN)

            # binarize
            arr = np.array(g, dtype=np.uint8)
            # adaptive-ish threshold using percentile
            t = int(np.percentile(arr, 35))
            bw = (arr < t).astype(np.uint8) * 255
            bw_img = Image.fromarray(bw).convert("L")

            for psm in psm_modes:
                txt = pytesseract.image_to_string(
                    bw_img,
                    config=f"--psm {psm} -c tessedit_char_whitelist=0123456789/",
                )
                m = CARD_NUMBER_PATTERN.search(txt or "")
                if not m:
                    continue
                num = int(m.group(1))
                total = int(m.group(2))
                # scoring: prefer plausible totals for WOTC, penalize years.
                score = 0.0
                if 20 <= total <= 500:
                    score += 2.0
                if total >= 50:
                    score += 1.0
                if num > 0:
                    score += 0.5
                if num > total + 150:
                    score -= 5.0
                # Penalize year-like captures (e.g. 1999/xxxx)
                if 1900 <= num <= 2099:
                    score -= 5.0
                if 1900 <= total <= 2099:
                    score -= 5.0

                # prefer minimal rotation magnitude
                score -= abs(ang) * 0.05

                if score > best_score:
                    best_score = score
                    best_num = f"{num}/{total}"
                    best_meta = {
                        "method": "wotc_fallback",
                        "source_crop": label,
                        "angle": ang,
                        "psm": psm,
                        "raw": txt.strip(),
                        "confidence": max(0.5, min(0.9, 0.5 + (score / 5.0))),
                    }

    return best_num, best_meta
