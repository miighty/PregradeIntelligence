"""Batch identity debug runner.

Usage:
  python3 scripts/batch_identity_debug.py /path/to/images/*.png

Prints OCR outputs + parsed identity. Optionally writes debug crops if you pass --out.

This script is intentionally simple to help iterate quickly with real sample images.
"""

from __future__ import annotations

import argparse
import glob
import os
from pathlib import Path

from PIL import Image

# Ensure repo root is on sys.path when running as a script.
import sys
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.card_identity import (
    extract_card_identity_from_path,
    _extract_region_text,
    _crop_region,
    NAME_REGION_A,
    NAME_REGION_B,
    CARD_NUMBER_REGION_LEFT,
    CARD_NUMBER_REGION_RIGHT,
    TESSERACT_NAME_CONFIG,
    TESSERACT_NUMBER_CONFIG,
)

from services.card_number import parse_card_number_from_crop


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("paths", nargs="+", help="Image paths or globs")
    p.add_argument("--out", help="Optional output dir for debug crops", default=None)
    args = p.parse_args()

    paths: list[str] = []
    for spec in args.paths:
        if any(ch in spec for ch in "*?["):
            paths.extend(glob.glob(spec))
        else:
            paths.append(spec)

    out_dir = Path(args.out) if args.out else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    for path in paths:
        print("\n===", path)
        ident = extract_card_identity_from_path(path)
        print("parsed:", ident)

        # raw OCR for tuning
        try:
            img = Image.open(path)
            img.load()
            name_raw_a = _extract_region_text(img, NAME_REGION_A, TESSERACT_NAME_CONFIG)
            name_raw_b = _extract_region_text(img, NAME_REGION_B, TESSERACT_NAME_CONFIG)
            num_r = _extract_region_text(img, CARD_NUMBER_REGION_RIGHT, TESSERACT_NUMBER_CONFIG)
            num_l = _extract_region_text(img, CARD_NUMBER_REGION_LEFT, TESSERACT_NUMBER_CONFIG)
            print("ocr.name.a:", repr(name_raw_a))
            print("ocr.name.b:", repr(name_raw_b))
            print("ocr.num.right:", repr(num_r))
            print("ocr.num.left:", repr(num_l))

            pr = parse_card_number_from_crop(_crop_region(img, CARD_NUMBER_REGION_RIGHT))
            pl = parse_card_number_from_crop(_crop_region(img, CARD_NUMBER_REGION_LEFT))
            print("tmpl.num.right:", pr)
            print("tmpl.num.left:", pl)

            if out_dir:
                stem = Path(path).stem
                w, h = img.size

                def crop(region, suffix):
                    left = int(w * region.left_ratio)
                    right = int(w * region.right_ratio)
                    top = int(h * region.top_ratio)
                    bottom = int(h * region.bottom_ratio)
                    c = img.crop((left, top, right, bottom))
                    c.save(out_dir / f"{stem}.{suffix}.png")

                crop(NAME_REGION_A, "name_a")
                crop(NAME_REGION_B, "name_b")
                crop(CARD_NUMBER_REGION_RIGHT, "num_right")
                crop(CARD_NUMBER_REGION_LEFT, "num_left")
        except Exception as e:
            print("debug error:", e)


if __name__ == "__main__":
    main()
