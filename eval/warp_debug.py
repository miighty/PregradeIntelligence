"""Warp debug: save quad overlay + warped card outputs with detailed metrics."""

from __future__ import annotations

import argparse
import json
import os
from typing import List, Dict, Any

import cv2
import numpy as np
from PIL import Image

from services.card_warp import (
    detect_card_quad_with_candidates,
    warp_card,
    QuadCandidate,
    _ASPECT_MIN_RELAXED,
    _ASPECT_MAX_RELAXED,
    _MIN_AREA_RATIO,
    _MAX_AREA_RATIO,
    _MIN_RECTANGULARITY,
)


IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

# Best-effort aspect tolerance: how much below _ASPECT_MIN_RELAXED we allow
_BEST_EFFORT_ASPECT_TOLERANCE = 0.05  # e.g. 0.58 - 0.05 = 0.53


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


def _draw_quad(
    bgr: np.ndarray,
    quad: np.ndarray,
    color: tuple[int, int, int] = (0, 255, 0),
    thickness: int = 3,
    label: str = "",
) -> None:
    """Draw a quad on the BGR image in-place."""
    pts = quad.astype(np.int32).reshape((-1, 1, 2))
    cv2.polylines(bgr, [pts], isClosed=True, color=color, thickness=thickness)
    if label:
        # Draw label near top-left corner
        tl = quad.astype(np.int32)[0]
        cv2.putText(bgr, label, (tl[0], max(tl[1] - 10, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)


def _draw_overlay(
    rgb: np.ndarray,
    chosen_quad: np.ndarray | None,
    candidates: List[QuadCandidate],
    debug: Dict[str, Any],
) -> np.ndarray:
    """Draw overlay with chosen quad (green) and top 3 other candidates (yellow)."""
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    # Sort candidates by score descending
    sorted_candidates = sorted(candidates, key=lambda c: c.score, reverse=True)

    # Draw top 3 non-chosen candidates in yellow
    drawn_count = 0
    for c in sorted_candidates:
        if drawn_count >= 3:
            break
        # Skip if this is the chosen quad
        if chosen_quad is not None and np.allclose(c.quad, chosen_quad, atol=1.0):
            continue
        label = f"#{drawn_count + 2} s={c.score:.2f} a={c.aspect:.2f} ar={c.area_ratio:.2f}"
        _draw_quad(bgr, c.quad, color=(0, 255, 255), thickness=2, label=label)
        drawn_count += 1

    # Draw chosen quad in green (on top)
    if chosen_quad is not None:
        chosen_label = f"CHOSEN s={debug.get('score', 0):.2f} a={debug.get('aspect', 0):.2f}"
        _draw_quad(bgr, chosen_quad, color=(0, 255, 0), thickness=3, label=chosen_label)
        # Draw corner labels
        labels = ["TL", "TR", "BR", "BL"]
        for i, pt in enumerate(chosen_quad.astype(np.int32)):
            cv2.putText(bgr, labels[i], tuple(pt), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    # Draw stats text at bottom
    h, w = bgr.shape[:2]
    stats_lines = [
        f"method={debug.get('method', '?')} pipeline={debug.get('pipeline', '?')} gate={debug.get('gate_mode', '?')}",
        f"area_ratio={debug.get('area_ratio', 0):.3f} aspect={debug.get('aspect', 0):.3f} rect={debug.get('rectangularity', 0):.3f}",
        f"center_dist={debug.get('center_dist', 0):.3f} score={debug.get('score', 0):.3f} candidates={debug.get('candidates_total', 0)}",
    ]
    y_offset = h - 60
    for line in stats_lines:
        cv2.putText(bgr, line, (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        y_offset += 18

    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def _find_best_effort_candidate(
    candidates: List[QuadCandidate],
) -> tuple[QuadCandidate | None, str]:
    """Find the best candidate that narrowly fails aspect only.
    
    Returns (candidate, reason) where reason explains why it was accepted.
    Only accepts candidates that:
    - Pass area_min, area_max, and rectangularity gates
    - Fail aspect by a small margin (within tolerance)
    """
    best: QuadCandidate | None = None
    reason = ""
    
    for c in candidates:
        # Must pass non-aspect gates
        if c.area_ratio < _MIN_AREA_RATIO:
            continue
        if c.area_ratio > _MAX_AREA_RATIO:
            continue
        if c.rectangularity < _MIN_RECTANGULARITY:
            continue
        
        # Check if it fails aspect within tolerance
        aspect_min_extended = _ASPECT_MIN_RELAXED - _BEST_EFFORT_ASPECT_TOLERANCE
        aspect_max_extended = _ASPECT_MAX_RELAXED + _BEST_EFFORT_ASPECT_TOLERANCE
        
        # Must fail normal relaxed aspect but pass extended
        fails_relaxed = not (_ASPECT_MIN_RELAXED <= c.aspect <= _ASPECT_MAX_RELAXED)
        passes_extended = aspect_min_extended <= c.aspect <= aspect_max_extended
        
        if fails_relaxed and passes_extended:
            if best is None or c.score > best.score:
                best = c
                if c.aspect < _ASPECT_MIN_RELAXED:
                    reason = f"aspect_low_{c.aspect:.3f}_vs_min_{_ASPECT_MIN_RELAXED}"
                else:
                    reason = f"aspect_high_{c.aspect:.3f}_vs_max_{_ASPECT_MAX_RELAXED}"
    
    return best, reason


def process_image(path: str, out_dir: str, best_effort_aspect: bool = False) -> Dict[str, Any]:
    """Process a single image and return stats.
    
    Args:
        path: Path to image file.
        out_dir: Output directory for debug artifacts.
        best_effort_aspect: If True, accept candidates that narrowly fail aspect.
    """
    img = Image.open(path)
    img.load()
    quad, debug, all_candidates = detect_card_quad_with_candidates(img)
    base = os.path.splitext(os.path.basename(path))[0]

    w, h = img.size

    stats: Dict[str, Any] = {
        "image": os.path.basename(path),
        "image_size": f"{w}x{h}",
        "quad_found": quad is not None,
        "method": debug.get("method", "none"),
        "pipeline": debug.get("pipeline", "none"),
        "gate_mode": debug.get("gate_mode", "none"),
        "score": debug.get("score"),
        "area_pct": round(debug.get("area_ratio", 0) * 100, 2) if debug.get("area_ratio") else None,
        "aspect": debug.get("aspect"),
        "rectangularity": debug.get("rectangularity"),
        "center_dist": debug.get("center_dist"),
        "candidates_total": debug.get("candidates_total", 0),
        "candidates_gated": debug.get("candidates_gated", 0),
        "reason": debug.get("reason"),
        "best_rejected": debug.get("best_rejected"),
        "gate_failures": debug.get("gate_failures"),
        "closest_rejected": debug.get("closest_rejected"),
    }

    # Always draw overlay with candidates (even if no quad chosen)
    rgb = np.array(img.convert("RGB"))
    overlay = _draw_overlay(rgb, quad, all_candidates, debug)
    overlay_path = os.path.join(out_dir, f"{base}__overlay.png")
    Image.fromarray(overlay).save(overlay_path)

    if quad is not None:
        try:
            warped = warp_card(img, quad)
            warped.save(os.path.join(out_dir, f"{base}__warped.png"))
            stats["warp_success"] = True
        except Exception as e:
            stats["warp_success"] = False
            stats["warp_error"] = str(e)
    else:
        stats["warp_success"] = False
        
        # Try best-effort if enabled and no quad found
        if best_effort_aspect and all_candidates:
            be_candidate, be_reason = _find_best_effort_candidate(all_candidates)
            if be_candidate is not None:
                stats["best_effort"] = True
                stats["best_effort_reason"] = be_reason
                stats["best_effort_aspect"] = round(be_candidate.aspect, 4)
                stats["best_effort_score"] = round(be_candidate.score, 4)
                try:
                    warped_be = warp_card(img, be_candidate.quad)
                    warped_be.save(os.path.join(out_dir, f"{base}__warped_best_effort.png"))
                    stats["best_effort_warp_success"] = True
                except Exception as e:
                    stats["best_effort_warp_success"] = False
                    stats["best_effort_warp_error"] = str(e)

    # Save debug JSON sidecar
    with open(os.path.join(out_dir, f"{base}__stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, sort_keys=True)

    return stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--front-dir", help="Directory containing images")
    ap.add_argument("--files", nargs="*", help="Explicit list of image files")
    ap.add_argument("--out-dir", default="eval/warp_debug_out")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument(
        "--best-effort-aspect",
        action="store_true",
        help="Accept candidates that narrowly fail aspect gate (eval-only, saves __warped_best_effort.png)",
    )
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    images: List[str] = []
    if args.files:
        images.extend(args.files)
    if args.front_dir:
        images.extend(discover_images(args.front_dir)[: args.limit])

    if not images:
        print("No images found.")
        return 2

    all_stats: List[Dict[str, Any]] = []
    success_count = 0
    best_effort_count = 0

    for path in images:
        if not os.path.exists(path):
            print(f"SKIP (not found): {path}")
            continue
        stats = process_image(path, args.out_dir, best_effort_aspect=args.best_effort_aspect)
        all_stats.append(stats)

        # Print per-image summary
        status = "OK" if stats["quad_found"] else "NO_QUAD"
        if stats.get("best_effort"):
            status = "BEST_EFFORT"
        area_pct = stats.get("area_pct", "?")
        aspect = stats.get("aspect", "?")
        rect = stats.get("rectangularity", "?")
        center_dist = stats.get("center_dist", "?")
        score = stats.get("score", "?")
        method = stats.get("method", "?")
        pipeline = stats.get("pipeline", "?")
        gate_mode = stats.get("gate_mode", "?")
        reason = stats.get("reason", "")
        best_rejected = stats.get("best_rejected", {})

        line = f"[{status}] {stats['image']}: method={method} pipeline={pipeline} gate={gate_mode}"
        line += f" area={area_pct}% aspect={aspect} rect={rect} cdist={center_dist} score={score}"
        if reason:
            line += f" reason={reason}"
        if stats.get("best_effort"):
            line += f" | BEST_EFFORT: aspect={stats.get('best_effort_aspect')} reason={stats.get('best_effort_reason')}"
        elif best_rejected:
            line += f" | REJECTED: aspect={best_rejected.get('aspect')} area={best_rejected.get('area_ratio')} rect={best_rejected.get('rectangularity')} cdist={best_rejected.get('center_dist')}"
        print(line)

        if stats["quad_found"]:
            success_count += 1
        if stats.get("best_effort"):
            best_effort_count += 1

    # Write summary JSON
    summary = {
        "total": len(all_stats),
        "success": success_count,
        "success_rate": round(success_count / len(all_stats) * 100, 2) if all_stats else 0,
        "best_effort_count": best_effort_count,
        "images": all_stats,
    }
    with open(os.path.join(args.out_dir, "_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    print(f"\nSummary: {success_count}/{len(all_stats)} ({summary['success_rate']}%) quads found")
    if best_effort_count > 0:
        print(f"Best-effort accepts: {best_effort_count}")
    print(f"Wrote outputs to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
