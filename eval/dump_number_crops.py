"""Dump the number-region crops used by services.card_identity.

Usage:
  ./.venv/bin/python eval/dump_number_crops.py --front-dir /Users/vr/Documents/cards/front --out-dir /tmp/pregrade_crops
"""

import argparse
import os
import sys

from PIL import Image

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from services.card_identity import _crop_region, CARD_NUMBER_REGION_RIGHT, CARD_NUMBER_REGION_LEFT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--front-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    for name in sorted(os.listdir(args.front_dir)):
        if not name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            continue
        path = os.path.join(args.front_dir, name)
        img = Image.open(path)
        img.load()
        rgb = img.convert("RGB")

        cr = _crop_region(rgb, CARD_NUMBER_REGION_RIGHT)
        cl = _crop_region(rgb, CARD_NUMBER_REGION_LEFT)

        base = os.path.splitext(name)[0]
        cr.save(os.path.join(args.out_dir, f"{base}__num_right.png"))
        cl.save(os.path.join(args.out_dir, f"{base}__num_left.png"))


if __name__ == "__main__":
    main()
