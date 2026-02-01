"""Batch card_number hit-rate measurement with resume support."""

from __future__ import annotations

import argparse
import json
import os
from typing import List, Dict, Any

from services.card_identity import extract_card_identity_from_path


IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def discover_images(dir_path: str) -> List[str]:
    files: List[str] = []
    for name in sorted(os.listdir(dir_path)):
        p = os.path.join(dir_path, name)
        if not os.path.isfile(p):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext in IMG_EXTS:
            files.append(p)
    return files


def load_checkpoint(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"index": 0, "hits": 0, "total": 0}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return {
                    "index": int(data.get("index", 0)),
                    "hits": int(data.get("hits", 0)),
                    "total": int(data.get("total", 0)),
                }
    except Exception:
        pass
    return {"index": 0, "hits": 0, "total": 0}


def save_checkpoint(path: str, state: Dict[str, Any]) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=True, sort_keys=True, indent=2)
    except Exception:
        return


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--front-dir", required=True)
    ap.add_argument("--batch-size", type=int, default=50)
    ap.add_argument("--resume-file", default="eval/number_hit_rate_warped.json")
    args = ap.parse_args()

    images = discover_images(args.front_dir)
    if not images:
        print("No images found.")
        return 2

    state = load_checkpoint(args.resume_file)
    start = min(state["index"], len(images))

    end = min(start + args.batch_size, len(images))
    for i in range(start, end):
        img_path = images[i]
        ident = extract_card_identity_from_path(img_path)
        state["total"] += 1
        if ident.card_number:
            state["hits"] += 1
        state["index"] = i + 1

    save_checkpoint(args.resume_file, state)
    hit_rate = (state["hits"] / state["total"] * 100.0) if state["total"] else 0.0
    print(f"Processed: {state['total']} | Hits: {state['hits']} | Hit-rate: {hit_rate:.2f}%")
    if state["index"] < len(images):
        print(f"Resume: next index {state['index']} of {len(images)}")
    else:
        print("Completed all images.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
