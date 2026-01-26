"""
Card Identity Detection Service

OCR-based card identity extraction for Pokémon cards.
Happy path implementation for clean, well-lit card front images.
"""

import re
from dataclasses import dataclass
from typing import Optional
import hashlib

import pytesseract
from PIL import Image
import numpy as np

from domain.types import CardIdentity


@dataclass(frozen=True)
class OCRRegion:
    """Defines a region of the image for targeted OCR extraction."""
    top_ratio: float
    bottom_ratio: float
    left_ratio: float
    right_ratio: float


NAME_REGION = OCRRegion(top_ratio=0.0, bottom_ratio=0.12, left_ratio=0.1, right_ratio=0.9)
NUMBER_REGION = OCRRegion(top_ratio=0.88, bottom_ratio=1.0, left_ratio=0.0, right_ratio=0.5)
SET_REGION = OCRRegion(top_ratio=0.88, bottom_ratio=1.0, left_ratio=0.5, right_ratio=1.0)

CARD_NUMBER_PATTERN = re.compile(r'(\d{1,3})\s*/\s*(\d{1,3})')


def extract_card_identity(image: Image.Image) -> CardIdentity:
    """
    Extract card identity from a Pokémon card front image.
    
    Args:
        image: PIL Image of the card front (clean, well-lit).
    
    Returns:
        CardIdentity with extracted fields and confidence score.
    """
    image_hash = _compute_image_hash(image)
    
    grayscale = image.convert('L')
    
    name_text = _extract_region_text(grayscale, NAME_REGION)
    number_text = _extract_region_text(grayscale, NUMBER_REGION)
    set_text = _extract_region_text(grayscale, SET_REGION)
    
    card_name = _parse_card_name(name_text)
    card_number = _parse_card_number(number_text)
    set_name = _parse_set_name(set_text, number_text)
    
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
    """
    Extract card identity from image bytes.
    
    Args:
        image_bytes: Raw image bytes (JPEG, PNG).
    
    Returns:
        CardIdentity with extracted fields and confidence score.
    """
    import io
    image = Image.open(io.BytesIO(image_bytes))
    return extract_card_identity(image)


def extract_card_identity_from_path(image_path: str) -> CardIdentity:
    """
    Extract card identity from an image file path.
    
    Args:
        image_path: Path to the card front image file.
    
    Returns:
        CardIdentity with extracted fields and confidence score.
    """
    image = Image.open(image_path)
    return extract_card_identity(image)


def _compute_image_hash(image: Image.Image) -> str:
    """Compute deterministic hash of image content for traceability."""
    arr = np.array(image.convert('RGB'))
    return hashlib.sha256(arr.tobytes()).hexdigest()


def _extract_region_text(image: Image.Image, region: OCRRegion) -> str:
    """Extract text from a specific region of the image."""
    width, height = image.size
    
    left = int(width * region.left_ratio)
    right = int(width * region.right_ratio)
    top = int(height * region.top_ratio)
    bottom = int(height * region.bottom_ratio)
    
    cropped = image.crop((left, top, right, bottom))
    
    config = '--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789/.- '
    text = pytesseract.image_to_string(cropped, config=config)
    
    return text.strip()


def _parse_card_name(raw_text: str) -> str:
    """Parse card name from OCR text."""
    if not raw_text:
        return ""
    
    cleaned = re.sub(r'[^A-Za-z\s\'-]', '', raw_text)
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


def _parse_set_name(set_text: str, number_text: str) -> str:
    """Parse set name from OCR text."""
    if set_text:
        cleaned = re.sub(r'[^A-Za-z\s\'-]', '', set_text)
        cleaned = ' '.join(cleaned.split())
        if len(cleaned) >= 3:
            return cleaned
    
    return "Unknown Set"


def _calculate_confidence(card_name: str, card_number: Optional[str], set_name: str) -> float:
    """
    Calculate confidence score based on extraction quality.
    
    Scoring:
    - Card name present and reasonable length: 0.4
    - Card number successfully parsed: 0.3
    - Set name identified (not Unknown): 0.3
    """
    score = 0.0
    
    if card_name and 3 <= len(card_name) <= 50:
        score += 0.4
    elif card_name:
        score += 0.2
    
    if card_number is not None:
        score += 0.3
    
    if set_name and set_name != "Unknown Set":
        score += 0.3
    
    return round(score, 2)
