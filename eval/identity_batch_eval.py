"""Batch identity extraction (resume) to avoid long-running OCR jobs getting killed.

This runs services.card_identity.extract_card_identity_from_path over a folder
in small batches and appends results to a CSV.

Usage:
  PYTHONPATH=. ./.venv/bin/python eval/identity_batch_eval.py \
    --images /path/to/fronts \
    --out eval/identity_results.csv \
    --batch-size 5

CSV columns:
  filename,card_name,card_number,set_name,confidence,match_method
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from services.card_identity import extract_card_identity_from_path


IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def iter_images(dirp: Path) -> list[Path]:
    return sorted([p for p in dirp.iterdir() if p.is_file() and p.suffix.lower() in IMG_EXTS])


def ensure_header(out_csv: Path):
    if out_csv.exists():
        return
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["filename", "card_name", "card_number", "set_name", "confidence", "match_method"])


def load_done(out_csv: Path) -> set[str]:
    if not out_csv.exists():
        return set()
    done = set()
    with out_csv.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            fn = (row.get("filename") or "").strip()
            if fn:
                done.add(fn)
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--batch-size", type=int, default=5)
    args = ap.parse_args()

    images_dir = Path(args.images)
    out_csv = Path(args.out)

    ensure_header(out_csv)
    done = load_done(out_csv)

    all_imgs = iter_images(images_dir)
    remaining = [p for p in all_imgs if p.name not in done]
    batch = remaining[: max(0, args.batch_size)]

    if not batch:
        print("No remaining images")
        return

    rows = []
    for p in batch:
        ident = extract_card_identity_from_path(str(p))
        rows.append([
            p.name,
            ident.card_name,
            ident.card_number,
            ident.set_name,
            ident.confidence,
            ident.match_method,
        ])

    with out_csv.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerows(rows)

    print(f"Appended {len(rows)} rows to {out_csv}")


if __name__ == "__main__":
    main()
