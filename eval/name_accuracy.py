"""Card name extraction accuracy evaluation.

Provides detailed metrics for debugging and improving name detection:
- Per-region hit rates
- Per-template-family accuracy
- Character accuracy analysis (Levenshtein distance)
- Common OCR confusion patterns

Usage:
    python eval/name_accuracy.py --front-dir path/to/images
    python eval/name_accuracy.py --front-dir path/to/images --ground-truth gt.csv
    python eval/name_accuracy.py --results-csv eval/identity_results.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from PIL import Image

from services.card_identity import (
    extract_card_identity_from_path,
    _detect_template_family,
    _name_regions_for_family,
    _crop_region,
    _extract_name_text,
    _parse_card_name,
    _best_name_from_list,
    _is_likely_pokemon_name,
    TESSERACT_NAME_CONFIG,
)
from services.card_warp import detect_card_quad, warp_card


IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class NameStats:
    """Statistics for name extraction."""
    total: int = 0
    extracted: int = 0  # Non-empty name returned
    correct: int = 0  # Matches ground truth (if available)
    partial_correct: int = 0  # Substring match
    levenshtein_sum: float = 0.0
    
    @property
    def extraction_rate(self) -> float:
        return (self.extracted / self.total * 100) if self.total else 0.0
    
    @property
    def accuracy(self) -> float:
        return (self.correct / self.total * 100) if self.total else 0.0
    
    @property
    def partial_accuracy(self) -> float:
        return ((self.correct + self.partial_correct) / self.total * 100) if self.total else 0.0
    
    @property
    def avg_levenshtein(self) -> float:
        return (self.levenshtein_sum / self.total) if self.total else 0.0


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    prev_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    
    return prev_row[-1]


def normalize_name(s: str) -> str:
    """Normalize name for comparison."""
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def discover_images(dir_path: str) -> List[str]:
    """Discover all image files in directory."""
    files: List[str] = []
    for name in sorted(os.listdir(dir_path)):
        p = os.path.join(dir_path, name)
        if not os.path.isfile(p):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext in IMG_EXTS:
            files.append(p)
    return files


def load_ground_truth(csv_path: str) -> Dict[str, str]:
    """Load ground truth card names from CSV.
    
    Expected CSV format: filename,card_name
    """
    gt: Dict[str, str] = {}
    if not csv_path or not os.path.exists(csv_path):
        return gt
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filename = row.get("filename", "").strip()
            name = row.get("card_name", "").strip()
            if filename and name:
                gt[filename] = name
    return gt


def extract_expected_from_filename(filename: str) -> Optional[str]:
    """Try to extract expected card name from filename.
    
    Handles patterns like:
    - "pikachu-base-set-bs-25.jpg" -> "Pikachu"
    - "dark-charizard-team-rocket-tr-4.jpg" -> "Dark Charizard"
    """
    base = os.path.splitext(filename)[0]
    
    # Remove common suffixes like set codes
    suffixes = [
        r"-[a-z]{2,4}-\d+$",  # -bs-25, -tr-4
        r"-\d+$",  # -25
        r"-[a-z0-9]+\d{4}[a-z0-9]*$",  # timestamps
    ]
    for pattern in suffixes:
        base = re.sub(pattern, "", base, flags=re.IGNORECASE)
    
    # Split on common set name patterns and take first part
    set_markers = [
        "base-set", "jungle", "fossil", "team-rocket", "gym-heroes",
        "gym-challenge", "neo-genesis", "neo-discovery", "neo-revelation",
        "neo-destiny", "expedition", "aquapolis", "skyridge", "ruby-sapphire",
        "sandstorm", "dragon", "magma-aqua", "hidden-legends", "firered-leafgreen",
        "team-rocket-returns", "deoxys", "emerald", "unseen-forces",
        "delta-species", "legend-maker", "holon-phantoms", "crystal-guardians",
        "dragon-frontiers", "power-keepers", "diamond-pearl", "mysterious-treasures",
        "secret-wonders", "great-encounters", "majestic-dawn", "legends-awakened",
        "stormfront", "platinum", "rising-rivals", "supreme-victors", "arceus",
        "heartgold-soulsilver", "unleashed", "undaunted", "triumphant",
        "call-of-legends", "black-white", "emerging-powers", "noble-victories",
        "next-destinies", "dark-explorers", "dragons-exalted", "boundaries-crossed",
        "plasma-storm", "plasma-freeze", "plasma-blast", "legendary-treasures",
        "x-y", "flashfire", "furious-fists", "phantom-forces", "primal-clash",
        "roaring-skies", "ancient-origins", "breakthrough", "breakpoint",
        "generations", "fates-collide", "steam-siege", "evolutions",
        "sun-moon", "guardians-rising", "burning-shadows", "shining-legends",
        "crimson-invasion", "ultra-prism", "forbidden-light", "celestial-storm",
        "dragon-majesty", "lost-thunder", "team-up", "unbroken-bonds",
        "unified-minds", "hidden-fates", "cosmic-eclipse", "sword-shield",
    ]
    
    name_part = base
    for marker in set_markers:
        idx = base.lower().find(marker)
        if idx > 0:
            name_part = base[:idx].rstrip("-")
            break
    
    # Convert to title case
    name = " ".join(word.capitalize() for word in name_part.split("-"))
    
    # Filter out garbage
    if len(name) < 2 or not any(c.isalpha() for c in name):
        return None
    
    return name


def evaluate_single_image(
    img_path: str,
    ground_truth: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate name extraction on a single image."""
    filename = os.path.basename(img_path)
    result: Dict[str, Any] = {
        "filename": filename,
        "detected_name": "",
        "template_family": "unknown",
        "region_results": {},
        "warp_success": False,
        "ground_truth": ground_truth,
        "correct": None,
        "partial_correct": None,
        "levenshtein": None,
    }
    
    try:
        img = Image.open(img_path)
        img.load()
    except Exception as e:
        result["error"] = str(e)
        return result
    
    # Try to warp the card
    quad, warp_debug = detect_card_quad(img)
    if quad is not None:
        try:
            warped = warp_card(img, quad)
            result["warp_success"] = True
            working_image = warped
        except Exception:
            working_image = img
    else:
        working_image = img
    
    # Detect template family
    template_family = _detect_template_family(working_image)
    result["template_family"] = template_family
    
    # Get name regions for this family
    name_regions = _name_regions_for_family(template_family)
    
    # Evaluate each region
    name_candidates: List[str] = []
    for i, region in enumerate(name_regions):
        raw = _extract_name_text(working_image, region)
        parsed = _parse_card_name(raw)
        
        result["region_results"][f"region_{i}"] = {
            "raw": raw[:100] if raw else "",
            "parsed": parsed,
            "is_likely_pokemon": _is_likely_pokemon_name(parsed),
        }
        name_candidates.append(parsed)
    
    # Select best name
    detected_name = _best_name_from_list(name_candidates)
    result["detected_name"] = detected_name
    
    # Compare against ground truth if available
    if ground_truth:
        norm_detected = normalize_name(detected_name)
        norm_gt = normalize_name(ground_truth)
        
        # Exact match
        result["correct"] = (norm_detected == norm_gt) if norm_detected else False
        
        # Partial match (substring)
        if norm_detected and norm_gt:
            result["partial_correct"] = (norm_detected in norm_gt or norm_gt in norm_detected)
        else:
            result["partial_correct"] = False
        
        # Levenshtein distance (normalized)
        if norm_gt:
            lev = levenshtein_distance(norm_detected, norm_gt)
            result["levenshtein"] = lev / max(len(norm_gt), 1)
    
    return result


def analyze_results_csv(csv_path: str, ground_truth: Dict[str, str]) -> List[Dict[str, Any]]:
    """Analyze existing results CSV file."""
    results = []
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filename = row.get("filename", "").strip()
            detected_name = row.get("card_name", "").strip()
            
            # Try to get ground truth
            gt = ground_truth.get(filename)
            if not gt:
                # Try to extract from filename
                gt = extract_expected_from_filename(filename)
            
            result = {
                "filename": filename,
                "detected_name": detected_name,
                "ground_truth": gt,
                "confidence": float(row.get("confidence", 0)),
                "correct": None,
                "partial_correct": None,
                "levenshtein": None,
            }
            
            if gt:
                norm_detected = normalize_name(detected_name)
                norm_gt = normalize_name(gt)
                
                result["correct"] = (norm_detected == norm_gt) if norm_detected else False
                
                if norm_detected and norm_gt:
                    result["partial_correct"] = (norm_detected in norm_gt or norm_gt in norm_detected)
                else:
                    result["partial_correct"] = False
                
                if norm_gt:
                    lev = levenshtein_distance(norm_detected, norm_gt)
                    result["levenshtein"] = lev / max(len(norm_gt), 1)
            
            results.append(result)
    
    return results


def aggregate_stats(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate individual results into summary statistics."""
    total = len(results)
    extracted = sum(1 for r in results if r.get("detected_name"))
    
    # Template family breakdown
    template_stats: Dict[str, NameStats] = defaultdict(NameStats)
    for r in results:
        family = r.get("template_family", "unknown")
        template_stats[family].total += 1
        if r.get("detected_name"):
            template_stats[family].extracted += 1
        if r.get("correct"):
            template_stats[family].correct += 1
        if r.get("partial_correct"):
            template_stats[family].partial_correct += 1
        if r.get("levenshtein") is not None:
            template_stats[family].levenshtein_sum += r["levenshtein"]
    
    # Ground truth stats
    gt_results = [r for r in results if r.get("ground_truth")]
    gt_correct = sum(1 for r in gt_results if r.get("correct"))
    gt_partial = sum(1 for r in gt_results if r.get("partial_correct") and not r.get("correct"))
    
    # Levenshtein stats
    lev_results = [r for r in results if r.get("levenshtein") is not None]
    avg_lev = sum(r["levenshtein"] for r in lev_results) / len(lev_results) if lev_results else 0
    
    # Confidence buckets for extracted names
    conf_buckets = defaultdict(int)
    for r in results:
        if r.get("detected_name"):
            conf = r.get("confidence", 0)
            if conf >= 0.9:
                conf_buckets["0.90-1.00"] += 1
            elif conf >= 0.7:
                conf_buckets["0.70-0.90"] += 1
            elif conf >= 0.5:
                conf_buckets["0.50-0.70"] += 1
            else:
                conf_buckets["<0.50"] += 1
    
    # Common OCR errors
    error_patterns: Dict[str, int] = defaultdict(int)
    for r in results:
        detected = r.get("detected_name", "")
        gt = r.get("ground_truth", "")
        if detected and gt and normalize_name(detected) != normalize_name(gt):
            # Record mismatches for analysis
            key = f"{gt[:20]} -> {detected[:20]}"
            error_patterns[key] += 1
    
    return {
        "total": total,
        "extracted": extracted,
        "extraction_rate": round(extracted / total * 100, 2) if total else 0,
        "ground_truth_evaluated": len(gt_results),
        "correct": gt_correct,
        "partial_correct": gt_partial,
        "accuracy": round(gt_correct / len(gt_results) * 100, 2) if gt_results else 0,
        "partial_accuracy": round((gt_correct + gt_partial) / len(gt_results) * 100, 2) if gt_results else 0,
        "avg_levenshtein": round(avg_lev, 3),
        "template_family_stats": {
            name: {
                "total": stats.total,
                "extracted": stats.extracted,
                "extraction_rate": round(stats.extraction_rate, 2),
                "correct": stats.correct,
                "accuracy": round(stats.accuracy, 2),
            }
            for name, stats in template_stats.items()
        },
        "confidence_distribution": dict(conf_buckets),
        "top_errors": dict(sorted(error_patterns.items(), key=lambda x: -x[1])[:20]),
    }


def print_report(stats: Dict[str, Any]) -> None:
    """Print a human-readable report."""
    print("=" * 70)
    print("CARD NAME EXTRACTION ACCURACY REPORT")
    print("=" * 70)
    
    print(f"\nOverall: {stats['extracted']}/{stats['total']} extracted ({stats['extraction_rate']:.2f}%)")
    
    if stats["ground_truth_evaluated"] > 0:
        print(f"\nGround Truth Evaluation ({stats['ground_truth_evaluated']} images):")
        print(f"  Exact match:   {stats['correct']}/{stats['ground_truth_evaluated']} ({stats['accuracy']:.2f}%)")
        print(f"  Partial match: {stats['correct'] + stats['partial_correct']}/{stats['ground_truth_evaluated']} ({stats['partial_accuracy']:.2f}%)")
        print(f"  Avg Levenshtein (normalized): {stats['avg_levenshtein']:.3f}")
    
    if stats.get("template_family_stats"):
        print("\n" + "-" * 70)
        print("PER-TEMPLATE-FAMILY STATS")
        print("-" * 70)
        for family, data in stats["template_family_stats"].items():
            print(f"  {family:15s}: {data['extracted']:4d}/{data['total']:4d} extracted ({data['extraction_rate']:5.2f}%)")
            if data.get("correct") is not None:
                print(f"                   {data['correct']:4d} correct ({data['accuracy']:5.2f}% accuracy)")
    
    if stats.get("confidence_distribution"):
        print("\n" + "-" * 70)
        print("CONFIDENCE DISTRIBUTION (extracted names)")
        print("-" * 70)
        for bucket, count in sorted(stats["confidence_distribution"].items()):
            bar = "#" * min(count // 2, 50)
            print(f"  {bucket}: {count:4d} {bar}")
    
    if stats.get("top_errors"):
        print("\n" + "-" * 70)
        print("TOP OCR ERRORS (expected -> got)")
        print("-" * 70)
        for error, count in list(stats["top_errors"].items())[:10]:
            print(f"  {error} (x{count})")
    
    print("\n" + "=" * 70)


def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluate card name extraction accuracy")
    ap.add_argument("--front-dir", help="Directory containing card front images")
    ap.add_argument("--results-csv", help="Analyze existing results CSV file")
    ap.add_argument("--ground-truth", help="CSV file with ground truth (filename,card_name)")
    ap.add_argument("--limit", type=int, default=0, help="Limit number of images (0=all)")
    ap.add_argument("--output-json", help="Save detailed results to JSON file")
    ap.add_argument("--verbose", action="store_true", help="Print per-image results")
    args = ap.parse_args()
    
    if not args.front_dir and not args.results_csv:
        print("Error: Must provide either --front-dir or --results-csv")
        return 1
    
    gt = load_ground_truth(args.ground_truth) if args.ground_truth else {}
    
    if args.results_csv:
        # Analyze existing results
        print(f"Analyzing results from {args.results_csv}...")
        results = analyze_results_csv(args.results_csv, gt)
    else:
        # Run fresh evaluation
        images = discover_images(args.front_dir)
        if not images:
            print("No images found.")
            return 2
        
        if args.limit > 0:
            images = images[:args.limit]
        
        print(f"Evaluating {len(images)} images...")
        
        results: List[Dict[str, Any]] = []
        for i, img_path in enumerate(images):
            filename = os.path.basename(img_path)
            ground_truth = gt.get(filename) or extract_expected_from_filename(filename)
            
            result = evaluate_single_image(img_path, ground_truth)
            results.append(result)
            
            if args.verbose:
                status = "HIT" if result.get("detected_name") else "MISS"
                name = result.get("detected_name") or "(none)"
                gt_name = result.get("ground_truth") or "?"
                match = "OK" if result.get("correct") else ("PARTIAL" if result.get("partial_correct") else "FAIL")
                print(f"[{status}] {filename}: '{name}' vs '{gt_name}' [{match}]")
            
            if (i + 1) % 50 == 0:
                print(f"  Processed {i + 1}/{len(images)}...")
    
    # Aggregate and report
    stats = aggregate_stats(results)
    print_report(stats)
    
    # Save detailed results if requested
    if args.output_json:
        output = {
            "summary": stats,
            "results": results,
        }
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, sort_keys=True)
        print(f"\nDetailed results saved to: {args.output_json}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
