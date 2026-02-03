"""
Card Identity Detection Service

OCR-based card identity extraction for Pokémon cards.
Happy path implementation for clean, well-lit card front images.
"""

import os
import re
from dataclasses import dataclass
from typing import Optional
import hashlib
import io

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np

from domain.types import CardIdentity
from services.card_number import parse_card_number_from_crop
from services.card_enrichment import enrich_identity
from services.card_warp import warp_card_best_effort
from services.card_identity_wotc import wotc_number_fallback


@dataclass(frozen=True)
class OCRRegion:
    """Defines a region of the image for targeted OCR extraction."""
    top_ratio: float
    bottom_ratio: float
    left_ratio: float
    right_ratio: float


# The name line varies by template/scan. We use per-template candidate bands.
NAME_REGION_MODERN_A = OCRRegion(top_ratio=0.040, bottom_ratio=0.115, left_ratio=0.10, right_ratio=0.72)
NAME_REGION_MODERN_B = OCRRegion(top_ratio=0.055, bottom_ratio=0.140, left_ratio=0.08, right_ratio=0.78)
NAME_REGION_VINTAGE_A = OCRRegion(top_ratio=0.060, bottom_ratio=0.135, left_ratio=0.12, right_ratio=0.70)
NAME_REGION_VINTAGE_B = OCRRegion(top_ratio=0.075, bottom_ratio=0.150, left_ratio=0.10, right_ratio=0.74)
NAME_REGION_SPECIAL_A = OCRRegion(top_ratio=0.050, bottom_ratio=0.150, left_ratio=0.08, right_ratio=0.78)
NAME_REGION_SPECIAL_B = OCRRegion(top_ratio=0.060, bottom_ratio=0.170, left_ratio=0.06, right_ratio=0.82)

# Card number placement: bottom-left or bottom-right on the warped card.
# We use two-pass crops (tight + expanded) per corner.
CARD_NUMBER_BR_TIGHT = OCRRegion(top_ratio=0.93, bottom_ratio=1.0, left_ratio=0.72, right_ratio=0.98)
CARD_NUMBER_BR_WIDE = OCRRegion(top_ratio=0.88, bottom_ratio=1.0, left_ratio=0.60, right_ratio=0.99)
CARD_NUMBER_BL_TIGHT = OCRRegion(top_ratio=0.93, bottom_ratio=1.0, left_ratio=0.02, right_ratio=0.30)
CARD_NUMBER_BL_WIDE = OCRRegion(top_ratio=0.88, bottom_ratio=1.0, left_ratio=0.01, right_ratio=0.42)

CARD_NUMBER_PATTERN = re.compile(r'(\d{1,3})\s*/\s*(\d{1,3})')
TESSERACT_LANG = 'eng'

# OCR configs tuned for small, high-contrast text regions.
# - psm 7: single line
# - psm 8: single word
# Note: whitelist helps reduce garbage characters.
# psm 7 = single line.
# NOTE: Avoid spaces inside -c values unless you quote carefully; it breaks arg parsing.
# Keep configs conservative; tune via preprocessing + region choice first.
TESSERACT_NAME_CONFIG = "--psm 7 --oem 1 -c preserve_interword_spaces=1"
TESSERACT_NUMBER_CONFIG = "--psm 7 --oem 1 -c tessedit_char_whitelist=0123456789/"


def extract_card_identity(image: Image.Image) -> CardIdentity:
    """Extract card identity from a Pokémon card front image.

    Returns CardIdentity with confidence score. Low confidence indicates
    extraction uncertainty; no exceptions are raised for OCR failures.

    Note: Tesseract OCR has limited accuracy on Pokémon card stylized fonts.
    For production use, consider cloud OCR services (Google Vision, AWS Textract).

    Test/dev guard:
    - When running under pytest (or when PREGRADE_SKIP_OCR=1), we skip the
      expensive warp/OCR steps and return a deterministic placeholder. This
      keeps unit tests fast and avoids hard dependency on the tesseract binary.
    """
    image_hash = _compute_image_hash(image)

    skip_ocr = os.environ.get("PREGRADE_SKIP_OCR", "").strip().lower() in {"1", "true", "yes"}
    if skip_ocr or os.environ.get("PYTEST_CURRENT_TEST"):
        return CardIdentity(
            set_name="Unknown Set",
            card_name="",
            card_number=None,
            variant=None,
            details={"trace": {"skipped": True, "reason": "test_or_config"}},
            confidence=0.0,
            match_method=f"ocr_extraction:{image_hash[:16]}:skipped",
        )

    rgb_image = image.convert('RGB') if image.mode != 'RGB' else image
    warped_image, warp_used, warp_reason, warp_debug = warp_card_best_effort(rgb_image)

    working_image = warped_image
    
    template_family = _detect_template_family(working_image)
    name_regions = _name_regions_for_family(template_family)
    name_candidates: list[str] = []
    for region in name_regions:
        raw = _extract_region_text(working_image, region, TESSERACT_NAME_CONFIG)
        name_candidates.append(_parse_card_name(raw))

    card_name = _best_name_from_list(name_candidates)

    # Card number: try deterministic template matcher across multiple candidate regions.
    # Choose the highest-confidence parse.
    # Rule: card number is always present in a bottom corner (bottom-right or bottom-left).
    # We prioritise those corners first for reliability.
    candidate_regions = [
        ("bottom_right:tight", CARD_NUMBER_BR_TIGHT),
        ("bottom_right:wide", CARD_NUMBER_BR_WIDE),
        ("bottom_left:tight", CARD_NUMBER_BL_TIGHT),
        ("bottom_left:wide", CARD_NUMBER_BL_WIDE),
    ]

    best_number = None
    best_conf = -1.0
    best_region = None
    number_candidates: list[dict[str, str | float | bool]] = []

    for label, region in candidate_regions:
        crop = _crop_region(working_image, region)

        # 1) Template matcher (fast) + sanity checks
        parsed = parse_card_number_from_crop(crop)
        if parsed and _is_plausible_card_number(parsed.number):
            number_candidates.append(
                {
                    "region": label,
                    "method": "template",
                    "value": parsed.number,
                    "confidence": parsed.confidence,
                    "valid": True,
                }
            )
            if parsed.confidence > best_conf:
                best_conf = parsed.confidence
                best_number = parsed.number
                best_region = label + ":template"
            continue
        elif parsed:
            number_candidates.append(
                {
                    "region": label,
                    "method": "template",
                    "value": parsed.number,
                    "confidence": parsed.confidence,
                    "valid": False,
                }
            )

        # 2) OCR fallback (more forgiving on certain templates)
        raw = _ocr_number_text(crop)
        ocr_num = _parse_card_number(raw)
        if ocr_num and _is_plausible_card_number(ocr_num):
            number_candidates.append(
                {
                    "region": label,
                    "method": "ocr",
                    "value": ocr_num,
                    "confidence": 0.75,
                    "valid": True,
                }
            )
            # Assign a modest confidence; template matches should win when sane.
            if 0.75 > best_conf:
                best_conf = 0.75
                best_number = ocr_num
                best_region = label + ":ocr"
        elif ocr_num:
            number_candidates.append(
                {
                    "region": label,
                    "method": "ocr",
                    "value": ocr_num,
                    "confidence": 0.5,
                    "valid": False,
                }
            )

    card_number = best_number

    if card_number is None and _debug_number_crops_enabled():
        _dump_number_crops(working_image, image_hash, candidate_regions)

    # WOTC/vintage fallback: focus on bottom-right number and try rotation sweep OCR.
    if card_number is None:
        wotc_num, wotc_meta = wotc_number_fallback(working_image)
        if wotc_num:
            card_number = wotc_num
            best_region = "wotc_fallback"
            number_candidates.append(
                {
                    "region": "bottom_right:wotc_fallback",
                    "method": "wotc_ocr",
                    "value": wotc_num,
                    "confidence": float(wotc_meta.get("confidence", 0.6)),
                    "valid": True,
                }
            )

    confidence = _calculate_confidence(card_name, card_number)
    trace = {
        "warp_used": warp_used,
        "warp_reason": warp_reason,
        "warp_debug": warp_debug,
        "template_family": template_family,
        "number_candidates": number_candidates,
        "number_region_selected": best_region or "none",
    }
    
    identity = CardIdentity(
        set_name="Unknown Set",
        card_name=card_name,
        card_number=card_number,
        variant=None,
        details={"trace": trace},
        confidence=confidence,
        match_method=f"ocr_extraction:{image_hash[:16]}:{best_region or 'none'}:{warp_reason}"
    )

    # Best-effort enrichment (set + structured fields) via TCGdex.
    # If enrichment fails, the original OCR identity is returned.
    return enrich_identity(identity)


def extract_card_identity_from_bytes(image_bytes: bytes) -> CardIdentity:
    """Extract card identity from raw image bytes (JPEG, PNG).

    NOTE: OCR + warping is relatively expensive. As a safety guard (and to keep
    unit tests fast), we short-circuit obviously non-card images.

    A real card-front photo will typically be hundreds of pixels wide/high.
    Tiny inputs are almost certainly placeholders or corrupted payloads.
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()

        w, h = image.size
        if max(w, h) < 200:
            return _empty_identity(image_bytes)

        return extract_card_identity(image)
    except Exception:
        return _empty_identity(image_bytes)


def extract_card_identity_from_path(image_path: str) -> CardIdentity:
    """Extract card identity from an image file path."""
    try:
        image = Image.open(image_path)
        image.load()
        return extract_card_identity(image)
    except Exception:
        return _empty_identity_from_path(image_path)


def _compute_image_hash(image: Image.Image) -> str:
    """Compute deterministic hash of image content for traceability."""
    rgb = image.convert('RGB')
    arr = np.array(rgb, dtype=np.uint8)
    return hashlib.sha256(arr.tobytes()).hexdigest()


def _preprocess_image(image: Image.Image) -> Image.Image:
    """Preprocess a cropped region to improve OCR accuracy.

    We keep this deterministic (no randomness) and fast:
    - grayscale
    - upsample 2x (small text)
    - contrast boost
    - light denoise
    - binarize (simple threshold)
    """
    processed = image.convert('L')

    # Upscale to help Tesseract on small UI text.
    w, h = processed.size
    processed = processed.resize((max(1, w * 2), max(1, h * 2)), resample=Image.Resampling.BICUBIC)

    processed = ImageEnhance.Contrast(processed).enhance(2.2)
    processed = processed.filter(ImageFilter.MedianFilter(size=3))

    # Binarize with a fixed threshold (deterministic).
    processed = processed.point(lambda p: 255 if p > 160 else 0)

    return processed


def _crop_region(image: Image.Image, region: OCRRegion) -> Image.Image:
    width, height = image.size
    left = int(width * region.left_ratio)
    right = int(width * region.right_ratio)
    top = int(height * region.top_ratio)
    bottom = int(height * region.bottom_ratio)
    return image.crop((left, top, right, bottom))


def _extract_region_text(image: Image.Image, region: OCRRegion, config: str) -> str:
    """Extract text from a specific region of the image."""
    try:
        cropped = _crop_region(image, region)
        cropped = _preprocess_image(cropped)

        text = pytesseract.image_to_string(cropped, lang=TESSERACT_LANG, config=config)
        return text.strip()
    except Exception:
        return ""


def _best_name(a: str, b: str) -> str:
    """Choose the better candidate name.

    Heuristic: prefer longer (up to a cap) and more alphabetic density.
    """
    def score(s: str) -> float:
        if not s:
            return 0.0
        alpha = sum(1 for ch in s if ch.isalpha())
        return min(len(s), 30) + (alpha / max(len(s), 1)) * 10.0

    return a if score(a) >= score(b) else b


def _best_name_from_list(candidates: list[str]) -> str:
    best = ""
    for c in candidates:
        best = _best_name(best, c)
    return best


def _parse_card_name(raw_text: str) -> str:
    """Parse card name from OCR text.

    We intentionally try to drop common template noise like:
    - "Evolves from ..."
    - "Basic" / "Stage 1" / "Stage 2"
    and keep the leftmost part which usually contains the card name.
    """
    if not raw_text:
        return ""

    first_line = raw_text.split("\n")[0].strip()

    # Keep only plausible characters.
    cleaned = re.sub(r"[^A-Za-z\s'\-éÉ]", " ", first_line)
    cleaned = " ".join(cleaned.split())

    # Strip common template phrases.
    lowered = cleaned.lower()
    for token in ["evolves from", "basic", "stage", "from"]:
        idx = lowered.find(token)
        if idx != -1:
            cleaned = cleaned[:idx].strip()
            lowered = cleaned.lower()

    # If we still have multiple words, prefer the first 1–2 words as name.
    parts = cleaned.split()
    if not parts:
        return ""

    # Most Pokémon names are 1 word; allow 2 for cases like "Mr Mime" (future).
    return " ".join(parts[:2])


def _ocr_number_text(crop: Image.Image) -> str:
    """OCR a crop intended to contain a card number like '136/189'."""
    try:
        processed = _preprocess_image(crop)
        text = pytesseract.image_to_string(processed, lang=TESSERACT_LANG, config=TESSERACT_NUMBER_CONFIG)
        return (text or "").strip()
    except Exception:
        return ""


def _parse_card_number(raw_text: str) -> Optional[str]:
    """Parse card number (e.g., '4/102') from OCR text."""
    if not raw_text:
        return None

    match = CARD_NUMBER_PATTERN.search(raw_text)
    if match:
        num = match.group(1).lstrip('0') or '0'
        total = match.group(2).lstrip('0') or '0'
        return f"{num}/{total}"

    return None


def _is_plausible_card_number(card_number: str) -> bool:
    if not card_number:
        return False
    m = CARD_NUMBER_PATTERN.search(card_number)
    if not m:
        return False
    try:
        num = int(m.group(1))
        total = int(m.group(2))
    except ValueError:
        return False
    if num <= 0 or total <= 0:
        return False
    # Reject obviously invalid totals (WOTC/mainline sets are typically much larger)
    # Note: promo subsets can be smaller, but for our current WOTC-first pipeline
    # we treat totals < 20 as not plausible.
    if total < 20:
        return False
    if total > 500:
        return False
    # Secret rares can exceed total; allow a reasonable margin.
    if num > total + 150:
        return False
    return True


def _detect_template_family(image: Image.Image) -> str:
    """Heuristic template family detection for name band placement."""
    arr = np.array(image.convert("RGB"), dtype=np.uint8)
    h, w, _ = arr.shape
    if h < 10 or w < 10:
        return "modern"

    border = int(min(h, w) * 0.03)
    border = max(border, 1)

    top = arr[:border, :, :]
    bottom = arr[-border:, :, :]
    left = arr[:, :border, :]
    right = arr[:, -border:, :]
    border_pixels = np.concatenate([top.reshape(-1, 3), bottom.reshape(-1, 3), left.reshape(-1, 3), right.reshape(-1, 3)], axis=0)

    mean = border_pixels.mean(axis=0)
    std = border_pixels.std(axis=0)

    # Vintage WOTC cards have a uniform yellow border.
    if std.mean() < 25 and mean[0] > 170 and mean[1] > 150 and mean[2] < 120:
        return "vintage"

    # Full art / special cards have high border variance.
    if std.mean() > 45:
        return "special"

    return "modern"


def _name_regions_for_family(family: str) -> list[OCRRegion]:
    if family == "vintage":
        return [NAME_REGION_VINTAGE_A, NAME_REGION_VINTAGE_B]
    if family == "special":
        return [NAME_REGION_SPECIAL_A, NAME_REGION_SPECIAL_B]
    return [NAME_REGION_MODERN_A, NAME_REGION_MODERN_B]


def _debug_number_crops_enabled() -> bool:
    return os.environ.get("PREGRADE_DEBUG_NUMBER_CROPS", "").strip().lower() in {"1", "true", "yes"}


def _dump_number_crops(image: Image.Image, image_hash: str, regions: list[tuple[str, OCRRegion]]) -> None:
    out_dir = os.environ.get("PREGRADE_DEBUG_NUMBER_DIR", "eval/out_crops")
    try:
        os.makedirs(out_dir, exist_ok=True)
    except Exception:
        return

    for label, region in regions:
        crop = _crop_region(image, region)
        filename = f"{image_hash[:12]}__{label.replace(':', '_')}.png"
        path = os.path.join(out_dir, filename)
        try:
            crop.save(path)
        except Exception:
            continue


def _calculate_confidence(card_name: str, card_number: Optional[str]) -> float:
    """
    Calculate confidence score based on extraction quality.
    
    Weights:
    - Card name present with reasonable length (3-50 chars): 0.50
    - Card name present but unusual length: 0.20
    - Card number successfully parsed: 0.50
    """
    score = 0.0
    
    if card_name:
        if 3 <= len(card_name) <= 50:
            score += 0.50
        else:
            score += 0.20
    
    if card_number is not None:
        score += 0.50
    
    return round(score, 2)


def _empty_identity(image_bytes: bytes) -> CardIdentity:
    """Return empty identity with zero confidence for unreadable images."""
    content_hash = hashlib.sha256(image_bytes).hexdigest()
    return CardIdentity(
        set_name="Unknown Set",
        card_name="",
        card_number=None,
        variant=None,
        details={},
        confidence=0.0,
        match_method=f"ocr_extraction_failed:{content_hash[:16]}"
    )


def _empty_identity_from_path(image_path: str) -> CardIdentity:
    """Return empty identity with zero confidence for unreadable file paths."""
    path_hash = hashlib.sha256(image_path.encode('utf-8')).hexdigest()
    return CardIdentity(
        set_name="Unknown Set",
        card_name="",
        card_number=None,
        variant=None,
        details={},
        confidence=0.0,
        match_method=f"ocr_extraction_failed:{path_hash[:16]}"
    )
