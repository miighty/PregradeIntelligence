"""Card number extraction accuracy evaluation.

Provides detailed metrics for debugging and improving number detection:
- Per-region hit rates (BR tight vs wide, BL tight vs wide)
- Per-template-family accuracy
- Confidence distribution and calibration
- False positive analysis

Usage:
    python eval/number_accuracy.py --front-dir path/to/images
    python eval/number_accuracy.py --front-dir path/to/images --ground-truth gt.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from PIL import Image

from services.card_identity import (
    extract_card_identity_from_path,
    _detect_template_family,
    _number_regions_for_family,
    _crop_region,
    CARD_NUMBER_BR_TIGHT,
    CARD_NUMBER_BR_WIDE,
    CARD_NUMBER_BL_TIGHT,
    CARD_NUMBER_BL_WIDE,
)
from services.card_number import parse_card_number_from_crop
from services.card_warp import detect_card_quad, warp_card


IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class RegionStats:
    """Statistics for a single number region."""
    attempts: int = 0
    hits: int = 0
    confidence_sum: float = 0.0
    confidences: List[float] = field(default_factory=list)
    
    @property
    def hit_rate(self) -> float:
        return (self.hits / self.attempts * 100) if self.attempts else 0.0
    
    @property
    def avg_confidence(self) -> float:
        return (self.confidence_sum / self.hits) if self.hits else 0.0


@dataclass
class TemplateStats:
    """Statistics for a template family."""
    total: int = 0
    hits: int = 0
    
    @property
    def hit_rate(self) -> float:
        return (self.hits / self.total * 100) if self.total else 0.0


@dataclass
class ConfidenceBucket:
    """Statistics for a confidence range."""
    total: int = 0
    correct: int = 0  # Would need ground truth to compute
    
    @property
    def accuracy(self) -> float:
        return (self.correct / self.total * 100) if self.total else 0.0


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
    """Load ground truth card numbers from CSV.
    
    Expected CSV format: filename,card_number
    """
    gt: Dict[str, str] = {}
    if not csv_path or not os.path.exists(csv_path):
        return gt
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filename = row.get("filename", "").strip()
            number = row.get("card_number", "").strip()
            if filename and number:
                gt[filename] = number
    return gt


def evaluate_single_image(
    img_path: str,
    ground_truth: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate number extraction on a single image.
    
    Returns detailed stats for aggregation.
    """
    filename = os.path.basename(img_path)
    result: Dict[str, Any] = {
        "filename": filename,
        "detected_number": None,
        "confidence": 0.0,
        "template_family": "unknown",
        "winning_region": None,
        "region_results": {},
        "warp_success": False,
        "correct": None,  # None if no ground truth
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
    
    # Get regions for this family
    candidate_regions = _number_regions_for_family(template_family)
    
    # Evaluate each region
    best_number = None
    best_conf = -1.0
    best_region = None
    
    all_regions = [
        ("bottom_right:tight", CARD_NUMBER_BR_TIGHT),
        ("bottom_right:wide", CARD_NUMBER_BR_WIDE),
        ("bottom_left:tight", CARD_NUMBER_BL_TIGHT),
        ("bottom_left:wide", CARD_NUMBER_BL_WIDE),
    ]
    
    for label, region in all_regions:
        crop = _crop_region(working_image, region)
        parsed = parse_card_number_from_crop(crop)
        
        region_result = {
            "detected": parsed.number if parsed else None,
            "confidence": parsed.confidence if parsed else 0.0,
            "in_family_order": any(label == r[0] for r in candidate_regions),
        }
        result["region_results"][label] = region_result
        
        if parsed and parsed.confidence > best_conf:
            best_conf = parsed.confidence
            best_number = parsed.number
            best_region = label
    
    result["detected_number"] = best_number
    result["confidence"] = best_conf
    result["winning_region"] = best_region
    
    # Check against ground truth if available
    if ground_truth:
        result["ground_truth"] = ground_truth
        result["correct"] = (best_number == ground_truth) if best_number else False
    
    return result


def aggregate_stats(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate individual results into summary statistics."""
    # Overall stats
    total = len(results)
    hits = sum(1 for r in results if r.get("detected_number"))
    warp_successes = sum(1 for r in results if r.get("warp_success"))
    
    # Per-region stats
    region_stats: Dict[str, RegionStats] = {
        "bottom_right:tight": RegionStats(),
        "bottom_right:wide": RegionStats(),
        "bottom_left:tight": RegionStats(),
        "bottom_left:wide": RegionStats(),
    }
    
    for r in results:
        for region_name, region_data in r.get("region_results", {}).items():
            if region_name in region_stats:
                stats = region_stats[region_name]
                stats.attempts += 1
                if region_data.get("detected"):
                    stats.hits += 1
                    conf = region_data.get("confidence", 0.0)
                    stats.confidence_sum += conf
                    stats.confidences.append(conf)
    
    # Per-template-family stats
    template_stats: Dict[str, TemplateStats] = defaultdict(TemplateStats)
    for r in results:
        family = r.get("template_family", "unknown")
        template_stats[family].total += 1
        if r.get("detected_number"):
            template_stats[family].hits += 1
    
    # Confidence distribution
    all_confidences = [r.get("confidence", 0.0) for r in results if r.get("detected_number")]
    conf_buckets = {
        "0.60-0.65": 0,
        "0.65-0.70": 0,
        "0.70-0.75": 0,
        "0.75-0.80": 0,
        "0.80-0.85": 0,
        "0.85-0.90": 0,
        "0.90-0.95": 0,
        "0.95-1.00": 0,
    }
    for c in all_confidences:
        if c < 0.65:
            conf_buckets["0.60-0.65"] += 1
        elif c < 0.70:
            conf_buckets["0.65-0.70"] += 1
        elif c < 0.75:
            conf_buckets["0.70-0.75"] += 1
        elif c < 0.80:
            conf_buckets["0.75-0.80"] += 1
        elif c < 0.85:
            conf_buckets["0.80-0.85"] += 1
        elif c < 0.90:
            conf_buckets["0.85-0.90"] += 1
        elif c < 0.95:
            conf_buckets["0.90-0.95"] += 1
        else:
            conf_buckets["0.95-1.00"] += 1
    
    # Ground truth accuracy (if available)
    gt_results = [r for r in results if r.get("correct") is not None]
    gt_correct = sum(1 for r in gt_results if r.get("correct"))
    
    return {
        "total": total,
        "hits": hits,
        "hit_rate": (hits / total * 100) if total else 0.0,
        "warp_success_rate": (warp_successes / total * 100) if total else 0.0,
        "region_stats": {
            name: {
                "attempts": stats.attempts,
                "hits": stats.hits,
                "hit_rate": round(stats.hit_rate, 2),
                "avg_confidence": round(stats.avg_confidence, 3),
            }
            for name, stats in region_stats.items()
        },
        "template_family_stats": {
            name: {
                "total": stats.total,
                "hits": stats.hits,
                "hit_rate": round(stats.hit_rate, 2),
            }
            for name, stats in template_stats.items()
        },
        "confidence_distribution": conf_buckets,
        "ground_truth_accuracy": {
            "evaluated": len(gt_results),
            "correct": gt_correct,
            "accuracy": round((gt_correct / len(gt_results) * 100) if gt_results else 0.0, 2),
        },
    }


def print_report(stats: Dict[str, Any]) -> None:
    """Print a human-readable report."""
    print("=" * 70)
    print("CARD NUMBER EXTRACTION ACCURACY REPORT")
    print("=" * 70)
    
    print(f"\nOverall: {stats['hits']}/{stats['total']} ({stats['hit_rate']:.2f}% hit rate)")
    print(f"Warp success rate: {stats['warp_success_rate']:.2f}%")
    
    print("\n" + "-" * 70)
    print("PER-REGION HIT RATES")
    print("-" * 70)
    for region, data in stats["region_stats"].items():
        print(f"  {region:25s}: {data['hits']:4d}/{data['attempts']:4d} ({data['hit_rate']:5.2f}%) avg_conf={data['avg_confidence']:.3f}")
    
    print("\n" + "-" * 70)
    print("PER-TEMPLATE-FAMILY HIT RATES")
    print("-" * 70)
    for family, data in stats["template_family_stats"].items():
        print(f"  {family:15s}: {data['hits']:4d}/{data['total']:4d} ({data['hit_rate']:5.2f}%)")
    
    print("\n" + "-" * 70)
    print("CONFIDENCE DISTRIBUTION (detections only)")
    print("-" * 70)
    for bucket, count in stats["confidence_distribution"].items():
        bar = "#" * min(count, 50)
        print(f"  {bucket}: {count:4d} {bar}")
    
    if stats["ground_truth_accuracy"]["evaluated"] > 0:
        gt = stats["ground_truth_accuracy"]
        print("\n" + "-" * 70)
        print("GROUND TRUTH ACCURACY")
        print("-" * 70)
        print(f"  Evaluated: {gt['evaluated']}")
        print(f"  Correct:   {gt['correct']}")
        print(f"  Accuracy:  {gt['accuracy']:.2f}%")
    
    print("\n" + "=" * 70)


def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluate card number extraction accuracy")
    ap.add_argument("--front-dir", required=True, help="Directory containing card front images")
    ap.add_argument("--ground-truth", help="CSV file with ground truth (filename,card_number)")
    ap.add_argument("--limit", type=int, default=0, help="Limit number of images (0=all)")
    ap.add_argument("--output-json", help="Save detailed results to JSON file")
    ap.add_argument("--verbose", action="store_true", help="Print per-image results")
    args = ap.parse_args()
    
    images = discover_images(args.front_dir)
    if not images:
        print("No images found.")
        return 2
    
    if args.limit > 0:
        images = images[:args.limit]
    
    gt = load_ground_truth(args.ground_truth) if args.ground_truth else {}
    
    print(f"Evaluating {len(images)} images...")
    
    results: List[Dict[str, Any]] = []
    for i, img_path in enumerate(images):
        filename = os.path.basename(img_path)
        ground_truth = gt.get(filename)
        
        result = evaluate_single_image(img_path, ground_truth)
        results.append(result)
        
        if args.verbose:
            status = "HIT" if result.get("detected_number") else "MISS"
            num = result.get("detected_number") or "(none)"
            conf = result.get("confidence", 0.0)
            region = result.get("winning_region") or "?"
            print(f"[{status}] {filename}: {num} (conf={conf:.2f}, region={region})")
        
        # Progress indicator
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
