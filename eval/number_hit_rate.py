"""Measure card_number extraction hit-rate WITHOUT running Tesseract.

This uses the deterministic template matcher (services.card_number.parse_card_number_from_crop)
across the same candidate regions used by services.card_identity.

Usage:
  PYTHONPATH=. ./.venv/bin/python eval/number_hit_rate.py --images /path/to/fronts --max 500
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path

from PIL import Image

from services.card_identity import (
    CARD_NUMBER_REGION_BOTTOM_LEFT,
    CARD_NUMBER_REGION_BOTTOM_RIGHT,
    CARD_NUMBER_REGION_TOP_LEFT,
    CARD_NUMBER_REGION_TOP_RIGHT,
    _crop_region,
)
from services.card_number import parse_card_number_from_crop


IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def iter_images(dirp: Path):
    for p in sorted(dirp.iterdir()):
        if p.is_file() and p.suffix.lower() in IMG_EXTS:
            yield p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True)
    ap.add_argument("--max", type=int, default=500)
    args = ap.parse_args()

    images_dir = Path(args.images)

    regions = [
        ("bottom_right", CARD_NUMBER_REGION_BOTTOM_RIGHT),
        ("bottom_left", CARD_NUMBER_REGION_BOTTOM_LEFT),
        ("top_right", CARD_NUMBER_REGION_TOP_RIGHT),
        ("top_left", CARD_NUMBER_REGION_TOP_LEFT),
    ]

    total = 0
    hits = 0
    confs = []

    for p in iter_images(images_dir):
        if total >= args.max:
            break
        total += 1

        im = Image.open(p)
        im.load()
        if max(im.size) > 1400:
            im.thumbnail((1400, 1400))
        rgb = im.convert("RGB")

        best = None
        best_region = None
        best_conf = -1.0

        for label, r in regions:
            crop = _crop_region(rgb, r)
            parsed = parse_card_number_from_crop(crop)
            if parsed and parsed.confidence > best_conf:
                best_conf = parsed.confidence
                best = parsed
                best_region = label

        if best:
            hits += 1
            confs.append(best.confidence)

    if confs:
        confs_sorted = sorted(confs)
        def q(pct: float):
            i = int(round((len(confs_sorted) - 1) * pct))
            return confs_sorted[i]
        print(
            {
                "total": total,
                "hits": hits,
                "hit_rate": round(hits / max(total, 1), 3),
                "conf_mean": round(sum(confs) / len(confs), 3),
                "conf_p10": q(0.10),
                "conf_p50": q(0.50),
                "conf_p90": q(0.90),
            }
        )
    else:
        print({"total": total, "hits": hits, "hit_rate": 0.0})


if __name__ == "__main__":
    main()
