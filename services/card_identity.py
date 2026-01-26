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


@dataclass(frozen=True)
class OCRRegion:
    """Defines a region of the image for targeted OCR extraction."""
    top_ratio: float
    bottom_ratio: float
    left_ratio: float
    right_ratio: float


NAME_REGION = OCRRegion(top_ratio=0.0, bottom_ratio=0.10, left_ratio=0.05, right_ratio=0.85)
FOOTER_REGION = OCRRegion(top_ratio=0.90, bottom_ratio=1.0, left_ratio=0.0, right_ratio=1.0)

CARD_NUMBER_PATTERN = re.compile(r'(\d{1,3})\s*/\s*(\d{1,3})')
TESSERACT_LANG = 'eng'
TESSERACT_NAME_CONFIG = '--psm 7 --oem 3'
TESSERACT_FOOTER_CONFIG = '--psm 6 --oem 3'


def extract_card_identity(image: Image.Image) -> CardIdentity:
    """
    Extract card identity from a Pokémon card front image.
    
    Returns CardIdentity with confidence score. Low confidence indicates
    extraction uncertainty; no exceptions are raised for OCR failures.
    """
    image_hash = _compute_image_hash(image)
    
    preprocessed = _preprocess_image(image)
    
    name_raw = _extract_region_text(preprocessed, NAME_REGION, TESSERACT_NAME_CONFIG)
    footer_raw = _extract_region_text(preprocessed, FOOTER_REGION, TESSERACT_FOOTER_CONFIG)
    
    card_name = _parse_card_name(name_raw)
    card_number = _parse_card_number(footer_raw)
    set_name = _parse_set_name(footer_raw)
    
    confidence = _calculate_confidence(card_name, card_number, set_name)
    
    return CardIdentity(
        set_name=set_name,
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
    """
    Preprocess image to improve OCR accuracy.
    Converts to grayscale, enhances contrast, and applies sharpening.
    """
    if image.mode != 'L':
        processed = image.convert('L')
    else:
        processed = image.copy()
    
    enhancer = ImageEnhance.Contrast(processed)
    processed = enhancer.enhance(1.5)
    
    processed = processed.filter(ImageFilter.SHARPEN)
    
    return processed


def _extract_region_text(image: Image.Image, region: OCRRegion, config: str) -> str:
    """Extract text from a specific region of the image."""
    try:
        width, height = image.size
        
        left = int(width * region.left_ratio)
        right = int(width * region.right_ratio)
        top = int(height * region.top_ratio)
        bottom = int(height * region.bottom_ratio)
        
        cropped = image.crop((left, top, right, bottom))
        
        text = pytesseract.image_to_string(cropped, lang=TESSERACT_LANG, config=config)
        return text.strip()
    except Exception:
        return ""


def _parse_card_name(raw_text: str) -> str:
    """Parse card name from OCR text, preserving valid Pokémon name characters."""
    if not raw_text:
        return ""
    
    first_line = raw_text.split('\n')[0].strip()
    cleaned = re.sub(r'[^A-Za-z\s\'\-é]', '', first_line)
    cleaned = ' '.join(cleaned.split())
    
    return cleaned


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


def _parse_set_name(footer_text: str) -> str:
    """
    Parse set name from footer OCR text.
    Returns 'Unknown Set' if no set name can be extracted.
    """
    if not footer_text:
        return "Unknown Set"
    
    lines = footer_text.split('\n')
    
    for line in lines:
        cleaned = re.sub(r'\d+\s*/\s*\d+', '', line)
        cleaned = re.sub(r'[^A-Za-z\s\'\-]', '', cleaned)
        cleaned = ' '.join(cleaned.split())
        
        if len(cleaned) >= 3:
            return cleaned
    
    return "Unknown Set"


def _calculate_confidence(card_name: str, card_number: Optional[str], set_name: str) -> float:
    """
    Calculate confidence score based on extraction quality.
    
    Weights:
    - Card name present with reasonable length (3-50 chars): 0.4
    - Card name present but unusual length: 0.15
    - Card number successfully parsed: 0.35
    - Set name identified (not 'Unknown Set'): 0.25
    """
    score = 0.0
    
    if card_name:
        if 3 <= len(card_name) <= 50:
            score += 0.40
        else:
            score += 0.15
    
    if card_number is not None:
        score += 0.35
    
    if set_name and set_name != "Unknown Set":
        score += 0.25
    
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
