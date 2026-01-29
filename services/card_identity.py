"""
Card Identity Detection Service

OCR-based card identity extraction for Pokémon cards.
Happy path implementation for clean, well-lit card front images.
"""

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


@dataclass(frozen=True)
class OCRRegion:
    """Defines a region of the image for targeted OCR extraction."""
    top_ratio: float
    bottom_ratio: float
    left_ratio: float
    right_ratio: float


# The name line varies by template/scan. We try multiple candidate bands near the top.
NAME_REGION_A = OCRRegion(top_ratio=0.045, bottom_ratio=0.115, left_ratio=0.10, right_ratio=0.72)
NAME_REGION_B = OCRRegion(top_ratio=0.060, bottom_ratio=0.140, left_ratio=0.08, right_ratio=0.78)

# Card number placement varies by era/template; try both corners.
CARD_NUMBER_REGION_RIGHT = OCRRegion(top_ratio=0.955, bottom_ratio=1.0, left_ratio=0.72, right_ratio=0.98)
CARD_NUMBER_REGION_LEFT = OCRRegion(top_ratio=0.955, bottom_ratio=1.0, left_ratio=0.02, right_ratio=0.32)

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
    """
    Extract card identity from a Pokémon card front image.
    
    Returns CardIdentity with confidence score. Low confidence indicates
    extraction uncertainty; no exceptions are raised for OCR failures.
    
    Note: Tesseract OCR has limited accuracy on Pokémon card stylized fonts.
    For production use, consider cloud OCR services (Google Vision, AWS Textract).
    """
    image_hash = _compute_image_hash(image)
    
    rgb_image = image.convert('RGB') if image.mode != 'RGB' else image
    
    # Try multiple name regions; choose the best-looking parse.
    name_raw_a = _extract_region_text(rgb_image, NAME_REGION_A, TESSERACT_NAME_CONFIG)
    name_raw_b = _extract_region_text(rgb_image, NAME_REGION_B, TESSERACT_NAME_CONFIG)

    card_name = _best_name(_parse_card_name(name_raw_a), _parse_card_name(name_raw_b))

    # Card number: try deterministic template matcher first (more reliable than OCR).
    number_crop_r = _crop_region(rgb_image, CARD_NUMBER_REGION_RIGHT)
    number_crop_l = _crop_region(rgb_image, CARD_NUMBER_REGION_LEFT)

    parsed_r = parse_card_number_from_crop(number_crop_r)
    parsed_l = parse_card_number_from_crop(number_crop_l)

    card_number = (parsed_r.number if parsed_r else None) or (parsed_l.number if parsed_l else None)
    
    confidence = _calculate_confidence(card_name, card_number)
    
    return CardIdentity(
        set_name="Unknown Set",
        card_name=card_name,
        card_number=card_number,
        variant=None,
        confidence=confidence,
        match_method=f"ocr_extraction:{image_hash[:16]}"
    )


def extract_card_identity_from_bytes(image_bytes: bytes) -> CardIdentity:
    """Extract card identity from raw image bytes (JPEG, PNG)."""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
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
        confidence=0.0,
        match_method=f"ocr_extraction_failed:{path_hash[:16]}"
    )
