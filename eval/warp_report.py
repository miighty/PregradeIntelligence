"""Warp report: read _summary.json and print diagnostic breakdown."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List


def load_summary(path: str) -> Dict[str, Any]:
    """Load summary JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def print_overview(summary: Dict[str, Any]) -> None:
    """Print overall success rate."""
    total = summary.get("total", 0)
    success = summary.get("success", 0)
    rate = summary.get("success_rate", 0)
    best_effort = summary.get("best_effort_count", 0)
    
    print("=" * 60)
    print("WARP DEBUG REPORT")
    print("=" * 60)
    print(f"Total images:     {total}")
    print(f"Successful warps: {success}")
    print(f"Success rate:     {rate}%")
    if best_effort > 0:
        print(f"Best-effort:      {best_effort}")
    print()


def print_gate_failure_breakdown(summary: Dict[str, Any]) -> None:
    """Print aggregated gate failure breakdown across all failed images."""
    images = summary.get("images", [])
    
    # Aggregate gate failures from all failed images
    total_aspect = 0
    total_area_min = 0
    total_area_max = 0
    total_rect = 0
    failed_count = 0
    
    for img in images:
        if img.get("quad_found"):
            continue
        failed_count += 1
        gate_failures = img.get("gate_failures", {})
        total_aspect += gate_failures.get("aspect", 0)
        total_area_min += gate_failures.get("area_min", 0)
        total_area_max += gate_failures.get("area_max", 0)
        total_rect += gate_failures.get("rectangularity", 0)
    
    if failed_count == 0:
        print("No failures to analyze.")
        print()
        return
    
    print("-" * 60)
    print(f"GATE FAILURE BREAKDOWN ({failed_count} failed images)")
    print("-" * 60)
    print(f"  aspect:        {total_aspect} candidates failed")
    print(f"  area_min:      {total_area_min} candidates failed")
    print(f"  area_max:      {total_area_max} candidates failed")
    print(f"  rectangularity: {total_rect} candidates failed")
    print()
    
    # Also show per-image primary failure reason (based on best_rejected flags)
    primary_reasons: Dict[str, int] = {
        "aspect_only": 0,
        "area_max_only": 0,
        "area_min_only": 0,
        "rect_only": 0,
        "multiple": 0,
        "no_candidates": 0,
    }
    
    for img in images:
        if img.get("quad_found"):
            continue
        best = img.get("best_rejected", {})
        if not best:
            primary_reasons["no_candidates"] += 1
            continue
        
        fails = []
        if best.get("failed_aspect_relaxed"):
            fails.append("aspect")
        if best.get("failed_area_min"):
            fails.append("area_min")
        if best.get("failed_area_max"):
            fails.append("area_max")
        if best.get("failed_rect"):
            fails.append("rect")
        
        if len(fails) == 0:
            # Shouldn't happen, but handle gracefully
            primary_reasons["no_candidates"] += 1
        elif len(fails) == 1:
            primary_reasons[f"{fails[0]}_only"] += 1
        else:
            primary_reasons["multiple"] += 1
    
    print("Primary rejection reason (best candidate):")
    for reason, count in sorted(primary_reasons.items(), key=lambda x: -x[1]):
        if count > 0:
            pct = round(count / failed_count * 100, 1)
            print(f"  {reason}: {count} ({pct}%)")
    print()


def print_worst_by_score(summary: Dict[str, Any], limit: int = 20) -> None:
    """Print top N worst images by lowest best_rejected.score."""
    images = summary.get("images", [])
    
    # Filter to failed images with best_rejected
    failed_with_score: List[tuple[str, float, Dict[str, Any]]] = []
    for img in images:
        if img.get("quad_found"):
            continue
        best = img.get("best_rejected", {})
        if best and best.get("score") is not None:
            failed_with_score.append((img["image"], best["score"], best))
    
    if not failed_with_score:
        return
    
    # Sort by score ascending (worst = lowest score)
    failed_with_score.sort(key=lambda x: x[1])
    
    print("-" * 60)
    print(f"TOP {min(limit, len(failed_with_score))} WORST BY LOWEST SCORE")
    print("-" * 60)
    for i, (name, score, best) in enumerate(failed_with_score[:limit], 1):
        aspect = best.get("aspect", "?")
        area = best.get("area_ratio", "?")
        rect = best.get("rectangularity", "?")
        print(f"{i:2}. {name}: score={score:.3f} aspect={aspect} area={area} rect={rect}")
    print()


def print_worst_by_area(summary: Dict[str, Any], limit: int = 20) -> None:
    """Print top N worst images by highest best_rejected.area_ratio."""
    images = summary.get("images", [])
    
    # Filter to failed images with best_rejected
    failed_with_area: List[tuple[str, float, Dict[str, Any]]] = []
    for img in images:
        if img.get("quad_found"):
            continue
        best = img.get("best_rejected", {})
        if best and best.get("area_ratio") is not None:
            failed_with_area.append((img["image"], best["area_ratio"], best))
    
    if not failed_with_area:
        return
    
    # Sort by area_ratio descending (worst = highest area = close-ups)
    failed_with_area.sort(key=lambda x: -x[1])
    
    print("-" * 60)
    print(f"TOP {min(limit, len(failed_with_area))} WORST BY HIGHEST AREA_RATIO")
    print("-" * 60)
    for i, (name, area, best) in enumerate(failed_with_area[:limit], 1):
        score = best.get("score", "?")
        aspect = best.get("aspect", "?")
        rect = best.get("rectangularity", "?")
        print(f"{i:2}. {name}: area={area:.4f} score={score} aspect={aspect} rect={rect}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description="Analyze warp debug summary JSON")
    ap.add_argument(
        "summary_path",
        nargs="?",
        default="eval/warp_debug_out/_summary.json",
        help="Path to _summary.json (default: eval/warp_debug_out/_summary.json)",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of worst images to show per list (default: 20)",
    )
    args = ap.parse_args()
    
    try:
        summary = load_summary(args.summary_path)
    except FileNotFoundError:
        print(f"Error: Summary file not found: {args.summary_path}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {args.summary_path}: {e}", file=sys.stderr)
        return 1
    
    print_overview(summary)
    print_gate_failure_breakdown(summary)
    print_worst_by_score(summary, limit=args.limit)
    print_worst_by_area(summary, limit=args.limit)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
