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
from services.pokemon_names import (
    get_all_pokemon_names,
    get_owner_prefixes,
    get_variant_prefixes,
    get_mechanic_suffixes,
    get_energy_types,
    get_energy_card_names,
    get_trainer_subtypes,
    get_trainer_card_names,
)


@dataclass(frozen=True)
class OCRRegion:
    """Defines a region of the image for targeted OCR extraction."""
    top_ratio: float
    bottom_ratio: float
    left_ratio: float
    right_ratio: float


# The name line varies by template/scan. We use per-template candidate bands.
# Pokemon card name regions (name at top-left, next to HP)
NAME_REGION_MODERN_A = OCRRegion(top_ratio=0.040, bottom_ratio=0.115, left_ratio=0.10, right_ratio=0.72)
NAME_REGION_MODERN_B = OCRRegion(top_ratio=0.055, bottom_ratio=0.140, left_ratio=0.08, right_ratio=0.78)
NAME_REGION_VINTAGE_A = OCRRegion(top_ratio=0.060, bottom_ratio=0.135, left_ratio=0.12, right_ratio=0.70)
NAME_REGION_VINTAGE_B = OCRRegion(top_ratio=0.075, bottom_ratio=0.150, left_ratio=0.10, right_ratio=0.74)
NAME_REGION_SPECIAL_A = OCRRegion(top_ratio=0.050, bottom_ratio=0.150, left_ratio=0.08, right_ratio=0.78)
NAME_REGION_SPECIAL_B = OCRRegion(top_ratio=0.060, bottom_ratio=0.170, left_ratio=0.06, right_ratio=0.82)

# Trainer card name regions (below "TRAINER" header, often with colored subtype badge)
# Trainer cards have: TRAINER header -> Card name -> Subtype badge (Item/Supporter/Stadium)
NAME_REGION_TRAINER_A = OCRRegion(top_ratio=0.08, bottom_ratio=0.16, left_ratio=0.08, right_ratio=0.92)
NAME_REGION_TRAINER_B = OCRRegion(top_ratio=0.10, bottom_ratio=0.18, left_ratio=0.06, right_ratio=0.94)
NAME_REGION_TRAINER_C = OCRRegion(top_ratio=0.06, bottom_ratio=0.14, left_ratio=0.10, right_ratio=0.90)

# Energy card name regions (energy type name near top, below "ENERGY" header)
NAME_REGION_ENERGY_A = OCRRegion(top_ratio=0.05, bottom_ratio=0.15, left_ratio=0.15, right_ratio=0.85)
NAME_REGION_ENERGY_B = OCRRegion(top_ratio=0.08, bottom_ratio=0.18, left_ratio=0.12, right_ratio=0.88)

# Header region for early card type detection (top banner with TRAINER/ENERGY/Pokemon name)
HEADER_REGION_TYPE_DETECT = OCRRegion(top_ratio=0.0, bottom_ratio=0.10, left_ratio=0.0, right_ratio=1.0)

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
TESSERACT_NAME_CONFIG_SINGLE = "--psm 8 --oem 1"  # Single word mode
TESSERACT_NUMBER_CONFIG = "--psm 7 --oem 1 -c tessedit_char_whitelist=0123456789/"

# Load comprehensive Pokemon names database (all 1025 species)
_POKEMON_NAMES: set[str] = get_all_pokemon_names()

# Load prefix/suffix registries for variant detection
_OWNER_PREFIXES: set[str] = get_owner_prefixes()
_VARIANT_PREFIXES: set[str] = get_variant_prefixes()
_MECHANIC_SUFFIXES: set[str] = get_mechanic_suffixes()

# Load Trainer card names database for validation
_TRAINER_CARD_NAMES: set[str] = get_trainer_card_names()
_TRAINER_SUBTYPES: set[str] = get_trainer_subtypes()

# Load Energy card names database for validation
_ENERGY_CARD_NAMES: set[str] = get_energy_card_names()
_ENERGY_TYPES: set[str] = get_energy_types()
_ENERGY_TYPES: set[str] = get_energy_types()
_TRAINER_SUBTYPES: set[str] = get_trainer_subtypes()

# Combined prefixes for parsing
_ALL_PREFIXES: set[str] = _OWNER_PREFIXES | _VARIANT_PREFIXES

# Common OCR confusions to correct
_OCR_CORRECTIONS: dict[str, str] = {
    "0": "o", "1": "l", "5": "s", "8": "b",
    "rn": "m", "cl": "d", "li": "h", "vv": "w",
}


def _normalize_for_match(s: str) -> str:
    """Normalize a string for fuzzy matching against Pokemon names."""
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def _normalize_preserve_spaces(s: str) -> str:
    """Normalize a string preserving spaces for prefix/suffix matching."""
    s = (s or "").strip().lower()
    # Keep apostrophes and spaces for owner prefix matching
    s = re.sub(r"[^a-z0-9\s'.\-]+", "", s)
    # Collapse multiple spaces
    s = " ".join(s.split())
    return s


def _extract_name_components(raw_name: str) -> tuple[list[str], str, list[str]]:
    """
    Extract prefixes, base Pokemon name, and suffixes from a card name.
    
    Returns: (prefixes, base_name, suffixes)
    
    Examples:
        "Team Rocket's Mewtwo ex" -> (["team rocket's"], "mewtwo", ["ex"])
        "Dark Charizard" -> (["dark"], "charizard", [])
        "Pikachu VMAX" -> ([], "pikachu", ["vmax"])
        "Alolan Ninetales GX" -> (["alolan"], "ninetales", ["gx"])
    """
    if not raw_name:
        return [], "", []
    
    normalized = _normalize_preserve_spaces(raw_name)
    words = normalized.split()
    
    if not words:
        return [], "", []
    
    prefixes: list[str] = []
    suffixes: list[str] = []
    base_words: list[str] = []
    
    # Extract prefixes (check multi-word prefixes first)
    i = 0
    while i < len(words):
        found_prefix = False
        # Check 3-word prefixes first (e.g., "team rocket's")
        for length in [3, 2, 1]:
            if i + length <= len(words):
                candidate = " ".join(words[i:i + length])
                # Check owner prefixes
                if candidate in _OWNER_PREFIXES or candidate + "'s" in _OWNER_PREFIXES:
                    prefixes.append(candidate)
                    i += length
                    found_prefix = True
                    break
                # Check variant prefixes
                if candidate in _VARIANT_PREFIXES:
                    prefixes.append(candidate)
                    i += length
                    found_prefix = True
                    break
        if not found_prefix:
            break
    
    # Extract suffixes from the end
    j = len(words) - 1
    while j >= i:
        found_suffix = False
        # Check multi-word suffixes (e.g., "tag team", "single strike")
        for length in [2, 1]:
            if j - length + 1 >= i:
                candidate = " ".join(words[j - length + 1:j + 1])
                if candidate in _MECHANIC_SUFFIXES:
                    suffixes.insert(0, candidate)
                    j -= length
                    found_suffix = True
                    break
        if not found_suffix:
            break
    
    # Remaining words are the base name
    base_words = words[i:j + 1]
    base_name = " ".join(base_words)
    
    return prefixes, base_name, suffixes


def _validate_base_pokemon_name(base_name: str) -> bool:
    """Check if a base name (without prefixes/suffixes) is a valid Pokemon name."""
    if not base_name:
        return False
    
    norm = _normalize_for_match(base_name)
    if not norm or len(norm) < 2:
        return False
    
    # Direct match
    if norm in _POKEMON_NAMES:
        return True
    
    # Check each word individually (for multi-word Pokemon names like "Mr. Mime")
    words = base_name.lower().split()
    for word in words:
        word_norm = _normalize_for_match(word)
        if word_norm and word_norm in _POKEMON_NAMES:
            return True
    
    # Substring match for partial OCR errors
    for pname in _POKEMON_NAMES:
        if len(pname) >= 5 and pname in norm:
            return True
        if len(norm) >= 5 and norm in pname:
            return True
    
    return False


def _reconstruct_card_name(prefixes: list[str], base_name: str, suffixes: list[str]) -> str:
    """Reconstruct a properly formatted card name from components."""
    parts = []
    
    # Format prefixes with proper capitalization
    for prefix in prefixes:
        if "'" in prefix:
            # Owner prefix: "Team Rocket's" -> "Team Rocket's"
            formatted = " ".join(word.capitalize() if not word.endswith("'s") else 
                                word[:-2].capitalize() + "'s" 
                                for word in prefix.split())
        else:
            # Variant prefix: "dark" -> "Dark"
            formatted = prefix.title()
        parts.append(formatted)
    
    # Format base name
    if base_name:
        parts.append(base_name.title())
    
    # Format suffixes (many are uppercase by convention)
    for suffix in suffixes:
        suffix_upper = suffix.upper()
        if suffix_upper in {"EX", "GX", "V", "VMAX", "VSTAR", "LV.X", "BREAK", "LEGEND", "PRIME"}:
            parts.append(suffix_upper)
        elif suffix_upper in {"TAG TEAM", "SINGLE STRIKE", "RAPID STRIKE", "FUSION STRIKE"}:
            parts.append(suffix.title())
        else:
            parts.append(suffix.lower())
    
    return " ".join(parts)


def _detect_card_type_from_text(text: str) -> str:
    """
    Detect card type (pokemon, trainer, energy) from OCR text.
    
    Returns: "pokemon", "trainer", "energy", or "unknown"
    """
    if not text:
        return "unknown"
    
    text_lower = text.lower()
    
    # Check for Trainer card indicators
    if "trainer" in text_lower:
        return "trainer"
    
    # Check for trainer subtypes
    for subtype in _TRAINER_SUBTYPES:
        if subtype in text_lower:
            return "trainer"
    
    # Check for Energy card indicators
    if "energy" in text_lower:
        # Could be Energy card or just energy cost text
        # Look for more specific patterns
        if re.search(r'\b(basic|special)\s+energy\b', text_lower):
            return "energy"
        # Check if it's just a Pokemon with energy type
        for etype in _ENERGY_TYPES:
            if f"{etype} energy" in text_lower:
                return "energy"
    
    # Check for Pokemon indicators (HP, attacks, etc.)
    if re.search(r'\bhp\s*\d+|\d+\s*hp\b', text_lower):
        return "pokemon"
    
    # Check if text contains a known Pokemon name
    for pname in _POKEMON_NAMES:
        if len(pname) >= 4 and pname in _normalize_for_match(text):
            return "pokemon"
    
    return "unknown"


def _detect_trainer_subtype(text: str) -> Optional[str]:
    """
    Detect the subtype of a Trainer card from OCR text.
    
    Returns: "item", "supporter", "stadium", "pokemon_tool", 
             "technical_machine", "ace_spec", or None
    """
    if not text:
        return None
    
    text_lower = text.lower()
    
    # Check for specific subtype indicators
    if "supporter" in text_lower:
        return "supporter"
    if "stadium" in text_lower:
        return "stadium"
    if "pokemon tool" in text_lower or "pokémon tool" in text_lower:
        return "pokemon_tool"
    if "technical machine" in text_lower or " tm " in text_lower:
        return "technical_machine"
    if "ace spec" in text_lower or "acespec" in text_lower:
        return "ace_spec"
    if "item" in text_lower:
        return "item"
    
    # Default to unknown if no specific subtype detected
    return None


def _detect_card_type_early(image: Image.Image) -> str:
    """
    Detect card type from header region BEFORE name extraction.
    
    This allows us to select the appropriate OCR regions for each card type:
    - Trainer cards have name below "TRAINER" header
    - Energy cards have energy type name/symbol
    - Pokemon cards have name at top-left with HP
    
    Returns: "pokemon", "trainer", "energy", or "unknown"
    """
    try:
        # Extract the header region (top 10% of card)
        crop = _crop_region(image, HEADER_REGION_TYPE_DETECT)
        
        # Try multiple preprocessing strategies for header OCR
        strategies = [
            ("--psm 6 --oem 1", crop),  # Block mode
            ("--psm 7 --oem 1", crop),  # Single line mode
        ]
        
        # Also try grayscale + contrast enhancement
        gray = crop.convert('L')
        enhanced = ImageEnhance.Contrast(gray).enhance(2.0)
        strategies.append(("--psm 6 --oem 1", enhanced))
        
        for config, img in strategies:
            try:
                text = pytesseract.image_to_string(img, lang=TESSERACT_LANG, config=config)
                text_lower = (text or "").lower()
                
                # Check for clear "TRAINER" indicator
                if "trainer" in text_lower:
                    return "trainer"
                
                # Check for "ENERGY" indicator
                if "energy" in text_lower:
                    return "energy"
                
                # Check for HP indicator (Pokemon cards have "HP" or "HP XXX")
                if re.search(r'\bhp\b|\d+\s*hp', text_lower):
                    return "pokemon"
                
            except Exception:
                continue
        
        # If no clear indicator found, check for Pokemon name in header
        # Pokemon cards typically have the Pokemon name prominently in the header
        for config, img in strategies[:1]:
            try:
                text = pytesseract.image_to_string(img, lang=TESSERACT_LANG, config=config)
                if text:
                    for pname in _POKEMON_NAMES:
                        if len(pname) >= 4 and pname in _normalize_for_match(text):
                            return "pokemon"
            except Exception:
                continue
        
        return "unknown"
        
    except Exception:
        return "unknown"


def _detect_energy_type_from_color(image: Image.Image) -> Optional[str]:
    """
    Detect energy type from dominant color in the card center.
    
    Basic Energy cards have a large colored energy symbol in the center.
    
    Returns: energy type string or None
    """
    try:
        # Sample the center region where energy symbol would be
        arr = np.array(image.convert("RGB"), dtype=np.uint8)
        h, w, _ = arr.shape
        
        # Center region (40-60% from top, 30-70% from sides)
        center = arr[int(h*0.4):int(h*0.6), int(w*0.3):int(w*0.7), :]
        
        # Calculate average color
        avg_color = center.mean(axis=(0, 1))
        r, g, b = avg_color
        
        # Map dominant colors to energy types
        # These thresholds are approximations based on energy card designs
        if g > r and g > b and g > 100:
            return "grass"
        if r > g and r > b and r > 150:
            if b > 100:
                return "psychic"  # Purple-ish
            return "fire"
        if b > r and b > g and b > 120:
            return "water"
        if r > 180 and g > 180 and b < 100:
            return "lightning"
        if r > 150 and g > 100 and b < 100:
            return "fighting"
        if r < 100 and g < 100 and b < 100:
            return "darkness"
        if r > 150 and g > 150 and b > 150:
            return "colorless"
        if r > 100 and g > 100 and b > 100 and abs(r - g) < 30 and abs(g - b) < 30:
            return "metal"
        
        return None
        
    except Exception:
        return None


def _name_regions_for_card_type(card_type: str, template_family: str) -> list[OCRRegion]:
    """
    Select appropriate name OCR regions based on detected card type.
    
    Different card types have names in different locations:
    - Pokemon: Top-left, before HP indicator
    - Trainer: Below "TRAINER" header, often centered
    - Energy: Energy type name, often centered below header
    """
    if card_type == "trainer":
        return [NAME_REGION_TRAINER_A, NAME_REGION_TRAINER_B, NAME_REGION_TRAINER_C]
    
    if card_type == "energy":
        return [NAME_REGION_ENERGY_A, NAME_REGION_ENERGY_B]
    
    # Default to Pokemon card regions based on template family
    return _name_regions_for_family(template_family)


def _is_likely_pokemon_name(name: str) -> bool:
    """
    Check if a name is likely a valid Pokemon card name.
    
    Handles various formats:
    - Simple names: "Pikachu", "Charizard"
    - Owner prefixes: "Brock's Onix", "Team Rocket's Mewtwo"
    - Variant prefixes: "Dark Charizard", "Alolan Ninetales"
    - Mechanic suffixes: "Pikachu ex", "Charizard VMAX"
    - Combinations: "Dark Alakazam ex", "Team Rocket's Mewtwo GX"
    """
    if not name:
        return False
    
    norm = _normalize_for_match(name)
    if not norm or len(norm) < 2:
        return False
    
    # Direct match against Pokemon names
    if norm in _POKEMON_NAMES:
        return True

    # Allow known prefixes/suffixes to count as "Pokemon-like" tokens in isolation
    # (useful for validating OCR fragments like "ex", "GX", "Dark").
    if norm in _VARIANT_PREFIXES or norm in _MECHANIC_SUFFIXES:
        return True
    
    # Try decomposing into components
    prefixes, base_name, suffixes = _extract_name_components(name)
    
    # If we found a valid base Pokemon name with recognized prefixes/suffixes, it's valid
    if base_name and _validate_base_pokemon_name(base_name):
        return True
    
    # Check if any known Pokemon name appears as a substring
    for pname in _POKEMON_NAMES:
        if len(pname) >= 4 and pname in norm:
            return True
        if len(norm) >= 4 and norm in pname:
            return True
    
    # Check individual words for Pokemon names
    words = name.lower().split()
    for word in words:
        word_norm = _normalize_for_match(word)
        if word_norm in _POKEMON_NAMES:
            return True
    
    return False


def _correct_ocr_confusions(text: str) -> str:
    """Apply common OCR confusion corrections."""
    result = text
    # Apply character-level corrections only for specific patterns
    for wrong, right in _OCR_CORRECTIONS.items():
        # Only correct in specific contexts (not blindly)
        if wrong in result.lower():
            # Check if correction would make it more Pokemon-like
            corrected = result.lower().replace(wrong, right)
            if _is_likely_pokemon_name(corrected) and not _is_likely_pokemon_name(result):
                result = corrected
    return result


def _looks_like_garbage_ocr(text: str) -> bool:
    """
    Check if OCR result looks like garbage (random characters, not a real name).
    
    Indicators of garbage OCR:
    - Too many uppercase letters in wrong places
    - Too many special characters
    - Repeating patterns that don't form words
    - Character sequences that are unlikely in English
    """
    if not text or len(text) < 2:
        return True
    
    # Count problematic characters
    special_count = sum(1 for c in text if not c.isalnum() and c not in " '-")
    if special_count > len(text) * 0.3:
        return True
    
    # Check for too many single-character "words"
    words = text.split()
    if len(words) > 2:
        single_char_words = sum(1 for w in words if len(w) == 1 and w.upper() not in "AI")
        if single_char_words > len(words) * 0.5:
            return True
    
    # Check for unlikely character sequences
    unlikely_patterns = ['xx', 'qq', 'zz', 'ww', 'vv', 'kk', 'yy']
    text_lower = text.lower()
    for pattern in unlikely_patterns:
        if pattern in text_lower:
            return True
    
    # Check consonant-heavy sequences (no vowels in long runs)
    vowels = set('aeiou')
    consonant_run = 0
    max_consonant_run = 0
    for c in text_lower:
        if c.isalpha():
            if c in vowels:
                consonant_run = 0
            else:
                consonant_run += 1
                max_consonant_run = max(max_consonant_run, consonant_run)
    
    # More than 5 consonants in a row is suspicious
    if max_consonant_run > 5:
        return True
    
    return False


def _extract_trainer_name(image: Image.Image) -> Optional[str]:
    """
    Extract Trainer card name using specialized OCR strategies.
    
    Trainer card names are typically:
    - Centered below the "TRAINER" header
    - In a bolder/larger font than Pokemon card names
    - May include special characters (', -, etc.)
    """
    best_candidate = None
    best_score = 0
    
    # Try each Trainer name region with multiple OCR configs
    trainer_regions = [NAME_REGION_TRAINER_A, NAME_REGION_TRAINER_B, NAME_REGION_TRAINER_C]
    
    for region in trainer_regions:
        crop = _crop_region(image, region)
        
        # Strategy 1: Standard grayscale + contrast
        gray = crop.convert('L')
        enhanced = ImageEnhance.Contrast(gray).enhance(2.0)
        
        configs = [
            "--psm 7 --oem 1",  # Single line
            "--psm 6 --oem 1",  # Block
            "--psm 8 --oem 1",  # Single word
        ]
        
        for config in configs:
            try:
                text = pytesseract.image_to_string(enhanced, lang=TESSERACT_LANG, config=config)
                text = (text or "").strip()
                
                if text and len(text) >= 3:
                    # Score this candidate
                    score = _score_trainer_name_candidate(text)
                    if score > best_score:
                        best_score = score
                        best_candidate = _clean_trainer_name(text)
            except Exception:
                continue
        
        # Strategy 2: High contrast binarization
        try:
            arr = np.array(gray, dtype=np.uint8)
            threshold = np.percentile(arr, 40)
            binary = Image.fromarray((arr > threshold).astype(np.uint8) * 255)
            
            for config in configs[:2]:
                text = pytesseract.image_to_string(binary, lang=TESSERACT_LANG, config=config)
                text = (text or "").strip()
                
                if text and len(text) >= 3:
                    score = _score_trainer_name_candidate(text)
                    if score > best_score:
                        best_score = score
                        best_candidate = _clean_trainer_name(text)
        except Exception:
            pass
    
    return best_candidate


def _is_likely_trainer_name(name: str) -> bool:
    """
    Check if a name is likely a valid Trainer card name.
    
    Checks against database of known Trainer card names and common patterns.
    """
    if not name or len(name) < 3:
        return False
    
    # Normalize preserving spaces for database lookup
    name_lower = (name or "").strip().lower()
    
    # Direct match in database (with spaces)
    if name_lower in _TRAINER_CARD_NAMES:
        return True
    
    # Also try without apostrophe variants
    name_no_apos = name_lower.replace("'", "")
    if name_no_apos in _TRAINER_CARD_NAMES:
        return True
    
    # Check if any multi-word segment matches
    for db_name in _TRAINER_CARD_NAMES:
        if len(db_name) >= 4 and db_name in name_lower:
            return True
    
    # Check for common Trainer card patterns (on original string for readability)
    trainer_patterns = [
        r"professor\s*'?s?\s*\w+",  # Professor's X, Professor X
        r"boss\s*'?s?\s*orders?",   # Boss's Orders
        r"\w+\s*ball",              # X Ball
        r"\w+\s*potion",            # X Potion
        r"\w+\s*city\s*gym",        # X City Gym
        r"team\s*\w+\s*grunt",      # Team X Grunt
    ]
    
    for pattern in trainer_patterns:
        if re.search(pattern, name_lower, re.IGNORECASE):
            return True
    
    return False


def _score_trainer_name_candidate(text: str) -> float:
    """
    Score a trainer name candidate based on likelihood of being correct.
    
    Higher scores indicate more likely real card names.
    """
    score = 0.0
    
    # Strong bonus for matching known Trainer card names
    if _is_likely_trainer_name(text):
        score += 5.0
    
    # Length-based scoring (Trainer names are typically 6-25 chars)
    length = len(text)
    if 6 <= length <= 25:
        score += 2.0
    elif 3 <= length < 6:
        score += 1.0
    elif length > 25:
        score += 0.5
    
    # Penalize garbage-looking text
    if _looks_like_garbage_ocr(text):
        score -= 3.0
    
    # Bonus for proper capitalization (Title Case or ALL CAPS)
    if text.istitle() or text.isupper():
        score += 1.0
    
    # Bonus for containing common trainer card words
    trainer_keywords = {'ball', 'potion', 'catcher', 'switch', 'trainer', 'professor', 
                       'boss', 'research', 'nest', 'ultra', 'quick', 'rare', 'candy',
                       'gym', 'stadium', 'supporter', 'energy', 'retrieval', 'search'}
    text_lower = text.lower()
    for keyword in trainer_keywords:
        if keyword in text_lower:
            score += 1.5
    
    # Penalize if it looks like a Pokemon name (probably wrong region)
    if _is_likely_pokemon_name(text):
        score -= 1.0
    
    return score


def _clean_trainer_name(text: str) -> str:
    """
    Clean up a trainer card name from OCR.
    
    - Remove extra whitespace
    - Fix common OCR issues
    - Normalize capitalization
    """
    # Remove leading/trailing whitespace and normalize internal spaces
    result = ' '.join(text.split())
    
    # Remove common OCR artifacts
    result = re.sub(r'^[^a-zA-Z]+', '', result)  # Leading non-letters
    result = re.sub(r'[^a-zA-Z\s\'-]+$', '', result)  # Trailing non-letters
    
    # Normalize to title case if it looks reasonable
    if result and not result.isupper():
        result = result.title()
    
    return result.strip()


def _is_likely_energy_name(name: str) -> bool:
    """
    Check if a name is likely a valid Energy card name.
    
    Checks against database of known Energy card names and common patterns.
    """
    if not name or len(name) < 3:
        return False
    
    name_lower = (name or "").strip().lower()
    
    # Direct match in database
    if name_lower in _ENERGY_CARD_NAMES:
        return True
    
    # Check if it's an energy type with optional "Energy" suffix
    for energy_type in _ENERGY_TYPES:
        if energy_type in name_lower:
            return True
    
    # Check for "Energy" keyword
    if "energy" in name_lower:
        return True
    
    return False


def _extract_energy_name(image: Image.Image, detected_type: Optional[str]) -> Optional[str]:
    """
    Extract Energy card name using OCR and/or color detection.
    
    Energy cards have simpler naming:
    - Basic Energy: "[Type] Energy" (e.g., "Fire Energy")
    - Special Energy: Name varies (e.g., "Double Colorless Energy")
    """
    # If we already detected the energy type via color analysis, use it
    if detected_type:
        return f"{detected_type.title()} Energy"
    
    # Otherwise try OCR on the energy name region
    best_candidate = None
    best_score = 0
    
    energy_regions = [NAME_REGION_ENERGY_A, NAME_REGION_ENERGY_B]
    
    for region in energy_regions:
        crop = _crop_region(image, region)
        
        # Try grayscale + contrast
        gray = crop.convert('L')
        enhanced = ImageEnhance.Contrast(gray).enhance(2.0)
        
        configs = [
            "--psm 7 --oem 1",
            "--psm 6 --oem 1",
        ]
        
        for config in configs:
            try:
                text = pytesseract.image_to_string(enhanced, lang=TESSERACT_LANG, config=config)
                text = (text or "").strip()
                
                if text and len(text) >= 3:
                    score = _score_energy_name_candidate(text)
                    if score > best_score:
                        best_score = score
                        best_candidate = _clean_energy_name(text)
            except Exception:
                continue
    
    return best_candidate


def _score_energy_name_candidate(text: str) -> float:
    """Score an energy name candidate based on likelihood of being correct."""
    score = 0.0
    
    # Strong bonus for matching known energy card names
    if _is_likely_energy_name(text):
        score += 5.0
    
    # Bonus for containing "energy"
    if "energy" in text.lower():
        score += 2.0
    
    # Bonus for matching energy type keywords
    text_lower = text.lower()
    for energy_type in _ENERGY_TYPES:
        if energy_type in text_lower:
            score += 2.0
            break
    
    # Penalize garbage
    if _looks_like_garbage_ocr(text):
        score -= 3.0
    
    return score


def _clean_energy_name(text: str) -> str:
    """Clean up an energy card name from OCR."""
    result = ' '.join(text.split())
    result = re.sub(r'^[^a-zA-Z]+', '', result)
    result = re.sub(r'[^a-zA-Z\s]+$', '', result)
    
    # Normalize to title case
    if result:
        result = result.title()
    
    return result.strip()


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
            card_type="unknown",
            trainer_subtype=None,
        )

    rgb_image = image.convert('RGB') if image.mode != 'RGB' else image
    warped_image, warp_used, warp_reason, warp_debug = warp_card_best_effort(rgb_image)

    working_image = warped_image
    
    # PHASE 1: Early card type detection BEFORE name extraction
    # This allows us to use type-specific OCR regions
    early_card_type = _detect_card_type_early(working_image)
    early_energy_type = None
    if early_card_type == "energy":
        early_energy_type = _detect_energy_type_from_color(working_image)
    
    template_family = _detect_template_family(working_image)
    
    # Select name regions based on detected card type
    name_regions = _name_regions_for_card_type(early_card_type, template_family)
    name_candidates: list[str] = []
    
    for region in name_regions:
        # Use improved multi-strategy name extraction
        raw = _extract_name_text(working_image, region)
        parsed = _parse_card_name(raw)
        name_candidates.append(parsed)
        
        # For Pokemon cards, early exit if we find a validated Pokemon name
        if early_card_type == "pokemon" and _is_likely_pokemon_name(parsed):
            break
        # For Trainer/Energy cards, accept any reasonable parsed name
        if early_card_type in ("trainer", "energy") and len(parsed) >= 3:
            break

    card_name = _best_name_from_list(name_candidates)
    
    # Fallback strategies depend on card type
    if early_card_type == "pokemon":
        # For Pokemon cards: try full-card OCR if no valid name found
        if not _is_likely_pokemon_name(card_name):
            full_card_name = _extract_name_from_full_card(working_image)
            if _is_likely_pokemon_name(full_card_name):
                card_name = full_card_name
    elif early_card_type == "trainer":
        # For Trainer cards: try additional OCR strategies if name looks bad
        if len(card_name) < 3 or _looks_like_garbage_ocr(card_name):
            trainer_name = _extract_trainer_name(working_image)
            if trainer_name and len(trainer_name) >= 3:
                card_name = trainer_name
    elif early_card_type == "energy":
        # For Energy cards: use specialized extraction if OCR failed
        if len(card_name) < 3 or _looks_like_garbage_ocr(card_name) or not _is_likely_energy_name(card_name):
            energy_name = _extract_energy_name(working_image, early_energy_type)
            if energy_name and len(energy_name) >= 3:
                card_name = energy_name

    # Card number: try deterministic template matcher across multiple candidate regions.
    # Choose the highest-confidence parse.
    # Rule: card number is always present in a bottom corner (bottom-right or bottom-left).
    # Region selection is adapted based on card type and template family for better hit rate.
    candidate_regions = _number_regions_for_card_type(early_card_type, template_family)

    best_number = None
    best_conf = -1.0
    best_region = None
    number_candidates: list[dict[str, str | float | bool]] = []

    for label, region in candidate_regions:
        crop = _crop_region(working_image, region)
        
        template_result = None
        ocr_result = None

        # 1) Template matcher (fast) + sanity checks
        parsed = parse_card_number_from_crop(crop)
        if parsed and _is_plausible_card_number(parsed.number):
            template_plausibility = _calculate_number_plausibility_score(parsed.number)
            number_candidates.append(
                {
                    "region": label,
                    "method": "template",
                    "value": parsed.number,
                    "confidence": parsed.confidence,
                    "plausibility": template_plausibility,
                    "valid": True,
                }
            )
            template_result = (parsed.number, parsed.confidence, template_plausibility)
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

        # 2) Always try OCR as well (template matcher can miss modern fonts)
        raw = _ocr_number_text(crop)
        ocr_num = _parse_card_number(raw)
        if ocr_num and _is_plausible_card_number(ocr_num):
            ocr_plausibility = _calculate_number_plausibility_score(ocr_num)
            # Higher confidence for OCR on modern/special cards with high plausibility
            ocr_conf = 0.85 if (template_family in ("special", "modern") and ocr_plausibility >= 0.9) else 0.80
            # Boost confidence further for larger totals (more reliable for modern sets)
            ocr_total = int(ocr_num.split("/")[1]) if "/" in ocr_num else 0
            if ocr_total >= 150:
                ocr_conf = min(1.0, ocr_conf + 0.15)  # Modern large sets
            number_candidates.append(
                {
                    "region": label,
                    "method": "ocr",
                    "value": ocr_num,
                    "confidence": ocr_conf,
                    "plausibility": ocr_plausibility,
                    "valid": True,
                }
            )
            ocr_result = (ocr_num, ocr_conf, ocr_plausibility)
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
        
        # 3) Choose between template and OCR results
        # For modern/special cards, OCR is often more reliable than template matching
        chosen_num = None
        chosen_conf = 0.0
        chosen_method = None
        
        if template_result and ocr_result:
            t_num, t_conf, t_plaus = template_result
            o_num, o_conf, o_plaus = ocr_result
            
            # Parse totals from both numbers
            t_total = int(t_num.split("/")[1]) if "/" in t_num else 0
            o_total = int(o_num.split("/")[1]) if "/" in o_num else 0
            
            # Decision logic:
            # 1. If OCR has significantly higher plausibility, prefer it
            # 2. For special/modern cards, prefer OCR when both are plausible
            # 3. Prefer larger totals (more common for modern sets)
            # 4. Otherwise prefer template (deterministic)
            
            if o_plaus > t_plaus + 0.1:
                chosen_num, chosen_conf, chosen_method = o_num, o_conf, "ocr"
            elif template_family in ("special", "modern") and o_plaus >= 0.9:
                # For modern/special cards, prefer OCR when it's confident
                # Larger totals are more common for recent sets
                if o_total > t_total:
                    chosen_num, chosen_conf, chosen_method = o_num, o_conf, "ocr"
                else:
                    chosen_num, chosen_conf, chosen_method = t_num, t_conf, "template"
            else:
                # Default to template
                chosen_num, chosen_conf, chosen_method = t_num, t_conf, "template"
        elif template_result:
            t_num, t_conf, t_plaus = template_result
            chosen_num, chosen_conf, chosen_method = t_num, t_conf, "template"
        elif ocr_result:
            o_num, o_conf, o_plaus = ocr_result
            chosen_num, chosen_conf, chosen_method = o_num, o_conf, "ocr"
        
        if chosen_num and chosen_conf > best_conf:
            best_conf = chosen_conf
            best_number = chosen_num
            best_region = f"{label}:{chosen_method}"

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
    
    # Card type detection: prefer early detection, fallback to full-card OCR
    # Early detection is faster and uses targeted header region
    detected_card_type = early_card_type if early_card_type != "unknown" else "pokemon"
    trainer_subtype = None
    
    # If early detection was uncertain, try full-card OCR as fallback
    if early_card_type == "unknown":
        try:
            full_ocr_text = pytesseract.image_to_string(
                working_image, lang=TESSERACT_LANG, config="--psm 6 --oem 1"
            )
            fallback_type = _detect_card_type_from_text(full_ocr_text)
            if fallback_type != "pokemon":  # Only override if we found something specific
                detected_card_type = fallback_type
        except Exception:
            pass
    
    # If detected as trainer, try to identify subtype
    if detected_card_type == "trainer":
        try:
            full_ocr_text = pytesseract.image_to_string(
                working_image, lang=TESSERACT_LANG, config="--psm 6 --oem 1"
            )
            trainer_subtype = _detect_trainer_subtype(full_ocr_text)
        except Exception:
            pass
    
    # Final validation: if we found a valid Pokemon name, it's likely a Pokemon card
    # unless early detection strongly indicated otherwise
    if _is_likely_pokemon_name(card_name) and early_card_type not in ("trainer", "energy"):
        detected_card_type = "pokemon"
    
    trace = {
        "warp_used": warp_used,
        "warp_reason": warp_reason,
        "warp_debug": warp_debug,
        "template_family": template_family,
        "number_candidates": number_candidates,
        "number_region_selected": best_region or "none",
        "early_card_type": early_card_type,
        "early_energy_type": early_energy_type,
        "detected_card_type": detected_card_type,
    }
    
    identity = CardIdentity(
        set_name="Unknown Set",
        card_name=card_name,
        card_number=card_number,
        variant=None,
        details={"trace": trace},
        confidence=confidence,
        match_method=f"ocr_extraction:{image_hash[:16]}:{best_region or 'none'}:{warp_reason}",
        card_type=detected_card_type,
        trainer_subtype=trainer_subtype,
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
    - adaptive binarize
    """
    processed = image.convert('L')

    # Upscale to help Tesseract on small UI text.
    w, h = processed.size
    processed = processed.resize((max(1, w * 2), max(1, h * 2)), resample=Image.Resampling.BICUBIC)

    processed = ImageEnhance.Contrast(processed).enhance(2.2)
    processed = processed.filter(ImageFilter.MedianFilter(size=3))

    # Adaptive binarize using percentile threshold (handles varying backgrounds)
    arr = np.array(processed, dtype=np.uint8)
    threshold = int(np.percentile(arr, 65))
    processed = processed.point(lambda p: 255 if p > threshold else 0)

    return processed


def _preprocess_name_region(image: Image.Image) -> list[Image.Image]:
    """Preprocess a name region with multiple strategies for OCR.
    
    Returns multiple preprocessed versions to try OCR on, ordered by likelihood.
    This increases hit rate without adding many OCR calls (we stop on first good result).
    """
    results: list[Image.Image] = []
    
    gray = image.convert('L')
    w, h = gray.size
    
    # Upscale 3x for better OCR on small text
    scale = 3
    gray = gray.resize((max(1, w * scale), max(1, h * scale)), resample=Image.Resampling.BICUBIC)
    
    arr = np.array(gray, dtype=np.uint8)
    
    # Strategy 1: High contrast with adaptive threshold (good for dark text on light bg)
    enhanced = ImageEnhance.Contrast(Image.fromarray(arr)).enhance(2.5)
    enhanced = enhanced.filter(ImageFilter.MedianFilter(size=3))
    enhanced_arr = np.array(enhanced, dtype=np.uint8)
    t1 = int(np.percentile(enhanced_arr, 60))
    binary1 = Image.fromarray(np.where(enhanced_arr > t1, 255, 0).astype(np.uint8))
    results.append(binary1)
    
    # Strategy 2: Lower threshold for lighter backgrounds
    t2 = int(np.percentile(enhanced_arr, 45))
    binary2 = Image.fromarray(np.where(enhanced_arr > t2, 255, 0).astype(np.uint8))
    results.append(binary2)
    
    # Strategy 3: Inverted (for light text on dark bg, less common but occurs on some cards)
    inverted = 255 - arr
    inv_enhanced = ImageEnhance.Contrast(Image.fromarray(inverted)).enhance(2.0)
    inv_arr = np.array(inv_enhanced, dtype=np.uint8)
    t3 = int(np.percentile(inv_arr, 55))
    binary3 = Image.fromarray(np.where(inv_arr > t3, 255, 0).astype(np.uint8))
    results.append(binary3)
    
    return results


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


def _extract_name_text(image: Image.Image, region: OCRRegion) -> str:
    """Extract name text with multiple preprocessing strategies.
    
    Tries multiple preprocessing approaches and OCR configs to maximize hit rate.
    Returns the best result based on validation heuristics.
    """
    try:
        cropped = _crop_region(image, region)
        
        candidates: list[str] = []
        
        # Strategy 1: Try raw image with multiple PSM modes (psm 6 often works best for names)
        raw_configs = [
            ("--psm 6 --oem 1", cropped),  # Block of text - often finds names in noisy backgrounds
            ("--psm 7 --oem 1 -c preserve_interword_spaces=1", cropped),  # Single line
        ]
        
        for config, img in raw_configs:
            try:
                text = pytesseract.image_to_string(img, lang=TESSERACT_LANG, config=config)
                text = (text or "").strip()
                if text and len(text) >= 2:
                    # Extract any Pokemon name from the noisy output
                    extracted = _extract_pokemon_name_from_text(text)
                    if extracted:
                        return extracted
                    candidates.append(text)
            except Exception:
                continue
        
        # Strategy 2: Try preprocessed versions
        preprocessed_versions = _preprocess_name_region(cropped)
        configs = [
            TESSERACT_NAME_CONFIG,
            "--psm 6 --oem 1",
        ]
        
        for prep_img in preprocessed_versions[:2]:
            for config in configs:
                try:
                    text = pytesseract.image_to_string(prep_img, lang=TESSERACT_LANG, config=config)
                    text = (text or "").strip()
                    if text and len(text) >= 2:
                        extracted = _extract_pokemon_name_from_text(text)
                        if extracted:
                            return extracted
                        candidates.append(text)
                except Exception:
                    continue
        
        # Return the best candidate
        if candidates:
            # Try to extract Pokemon name from any candidate
            for c in candidates:
                extracted = _extract_pokemon_name_from_text(c)
                if extracted:
                    return extracted
            return max(candidates, key=len)
        return ""
    except Exception:
        return ""


def _extract_pokemon_name_from_text(text: str) -> str:
    """Extract a valid Pokemon name from noisy OCR output.
    
    Scans the text for any known Pokemon names and returns the best match.
    """
    if not text:
        return ""
    
    # Normalize for matching
    text_lower = text.lower()
    text_clean = re.sub(r"[^a-z\s]", " ", text_lower)
    words = text_clean.split()
    
    # Check each word against known Pokemon names
    for word in words:
        if len(word) >= 3 and word in _POKEMON_NAMES:
            # Found a Pokemon name - return it properly capitalized
            return word.capitalize()
    
    # Check for multi-word Pokemon names
    text_joined = " ".join(words)
    for pname in _POKEMON_NAMES:
        if len(pname) >= 4 and pname in text_joined:
            return pname.capitalize()
    
    # Check if any word is close to a Pokemon name (1-2 char difference)
    for word in words:
        if len(word) >= 4:
            for pname in _POKEMON_NAMES:
                if len(pname) >= 4 and abs(len(word) - len(pname)) <= 2:
                    # Simple similarity check
                    matches = sum(1 for a, b in zip(word, pname) if a == b)
                    if matches >= len(pname) * 0.7:
                        return pname.capitalize()
    
    return ""


def _extract_name_from_full_card(image: Image.Image) -> str:
    """Extract Pokemon name from full card OCR as fallback.
    
    For cards with highly stylized fonts where the name region OCR fails,
    the name often appears elsewhere on the card (in ability text, rules, etc).
    """
    try:
        # Full card OCR
        text = pytesseract.image_to_string(image, lang=TESSERACT_LANG, config="--psm 6 --oem 1")
        if not text:
            return ""
        
        # Search for any known Pokemon name in the text
        return _extract_pokemon_name_from_text(text)
    except Exception:
        return ""


def _best_name(a: str, b: str) -> str:
    """Choose the better candidate name.

    Heuristic: prefer validated Pokemon names, then longer with good alphabetic density.
    """
    score_a = _score_name_candidate(a)
    score_b = _score_name_candidate(b)
    return a if score_a >= score_b else b


def _best_name_from_list(candidates: list[str]) -> str:
    """Select the best name from a list of candidates."""
    if not candidates:
        return ""
    
    # Prefer validated Pokemon names first
    for c in candidates:
        if c and _is_likely_pokemon_name(c):
            return c
    
    # Fall back to scoring
    best = ""
    best_score = -1.0
    for c in candidates:
        if not c:
            continue
        score = _score_name_candidate(c)
        if score > best_score:
            best_score = score
            best = c
    
    return best


def _parse_card_name(raw_text: str) -> str:
    """Parse card name from OCR text.

    Handles various Pokemon TCG card name formats:
    - Simple names: "Pikachu", "Charizard"
    - Owner prefixes: "Brock's Onix", "Team Rocket's Mewtwo"
    - Variant prefixes: "Dark Charizard", "Alolan Ninetales"
    - Mechanic suffixes: "Pikachu ex", "Charizard VMAX"
    - Combinations: "Dark Alakazam ex", "Team Rocket's Mewtwo GX"
    
    Supports names up to 6 words and 50 characters.

    We intentionally try to drop common template noise like:
    - "Evolves from ..."
    - "Basic" / "Stage 1" / "Stage 2"
    - HP values, attack names
    """
    if not raw_text:
        return ""

    first_line = raw_text.split("\n")[0].strip()

    # Keep only plausible characters (including apostrophes for owner names)
    cleaned = re.sub(r"[^A-Za-z\s'\-éÉ.]", " ", first_line)
    cleaned = " ".join(cleaned.split())

    # Strip common template phrases.
    lowered = cleaned.lower()
    noise_tokens = [
        "evolves from", "stage 2", "stage 1", "stage", "basic pokemon",
        "from", "hp ", " hp", "weakness", "resistance", "retreat",
        "put", "damage", "attack",
    ]
    for token in noise_tokens:
        idx = lowered.find(token)
        if idx != -1:
            cleaned = cleaned[:idx].strip()
            lowered = cleaned.lower()

    parts = cleaned.split()
    if not parts:
        return ""

    # Increased limit: support up to 6 words for complex names
    # e.g., "Team Rocket's Dark Alakazam ex"
    max_words = min(7, len(parts) + 1)
    
    best_name = ""
    best_score = -1
    
    # Try different word combinations, preferring longer valid names
    for num_words in range(1, max_words):
        candidate = " ".join(parts[:num_words])
        
        # Skip if candidate exceeds 50 character limit
        if len(candidate) > 50:
            continue
        
        # Try to decompose and validate
        prefixes, base_name, suffixes = _extract_name_components(candidate)
        
        # Strong preference if we can extract a valid base Pokemon name
        if base_name and _validate_base_pokemon_name(base_name):
            reconstructed = _reconstruct_card_name(prefixes, base_name, suffixes)
            # Score boost for having recognizable structure
            score = _score_name_candidate(candidate) + 15.0
            if prefixes:
                score += 5.0  # Bonus for recognized prefix
            if suffixes:
                score += 3.0  # Bonus for recognized suffix
            if score > best_score:
                best_score = score
                best_name = reconstructed if reconstructed else candidate
        else:
            score = _score_name_candidate(candidate)
            if score > best_score:
                best_score = score
                best_name = candidate
    
    # Apply OCR corrections if the result doesn't look like a Pokemon name
    if not _is_likely_pokemon_name(best_name):
        corrected = _correct_ocr_confusions(best_name)
        if _is_likely_pokemon_name(corrected):
            # Re-parse with corrections to get proper formatting
            prefixes, base_name, suffixes = _extract_name_components(corrected)
            if base_name:
                best_name = _reconstruct_card_name(prefixes, base_name, suffixes)
            else:
                best_name = corrected.title()
    
    return best_name


def _score_name_candidate(name: str) -> float:
    """Score a name candidate for likelihood of being a valid Pokemon card name.
    
    Supports longer names (up to 50 chars) with owner prefixes, variant prefixes,
    and mechanic suffixes.
    """
    if not name:
        return 0.0
    
    score = 0.0
    norm = _normalize_for_match(name)
    words = name.lower().split()
    
    # Length scoring - increased to support longer variant names
    # e.g., "Team Rocket's Mewtwo ex" = 24 chars
    if 3 <= len(name) <= 50:
        score += 2.0
        # Slight preference for moderate lengths
        if 5 <= len(name) <= 30:
            score += 1.0
    elif len(name) > 50:
        score -= 1.0
    
    # Alphabetic density (prefer mostly letters, allow apostrophes and spaces)
    valid_chars = sum(1 for c in name if c.isalpha() or c in " '-.")
    alpha_ratio = valid_chars / max(len(name), 1)
    score += alpha_ratio * 3.0
    
    # Try to decompose into components for structured scoring
    prefixes, base_name, suffixes = _extract_name_components(name)
    
    # Strong bonus for valid base Pokemon name
    if base_name and _validate_base_pokemon_name(base_name):
        score += 12.0
        # Additional bonus for recognized prefixes
        if prefixes:
            score += 4.0 * len(prefixes)
        # Additional bonus for recognized suffixes  
        if suffixes:
            score += 3.0 * len(suffixes)
    else:
        # Fallback: check individual words
        pokemon_match_count = 0
        modifier_match_count = 0
        
        for word in words:
            word_norm = _normalize_for_match(word)
            if word_norm in _POKEMON_NAMES:
                pokemon_match_count += 1
                score += 10.0  # Full Pokemon name
            elif word_norm in _MECHANIC_SUFFIXES:
                modifier_match_count += 1
                score += 2.0   # Mechanic suffix
            elif word in _normalize_preserve_spaces(name):
                # Check against variant/owner prefixes
                for prefix in _ALL_PREFIXES:
                    if word_norm in _normalize_for_match(prefix):
                        modifier_match_count += 1
                        score += 2.0
                        break
        
        # Bonus for multi-word names with Pokemon matches (like "Dark Charizard")
        if pokemon_match_count >= 1 and modifier_match_count >= 1:
            score += 5.0
        
        # Substring match fallback
        if pokemon_match_count == 0:
            for pname in _POKEMON_NAMES:
                if len(pname) >= 5 and (pname in norm or norm in pname):
                    score += 5.0
                    break
    
    # Penalize garbage patterns
    if re.search(r"[A-Z]{5,}", name):  # Many consecutive capitals (increased threshold)
        score -= 2.0
    if re.search(r"(.)\1{3,}", name.lower()):  # 4+ repeated characters
        score -= 2.0
    if re.search(r"\d{3,}", name):  # 3+ consecutive digits
        score -= 3.0
    
    return score


def _ocr_number_text(crop: Image.Image) -> str:
    """OCR a crop intended to contain a card number like '136/189'.
    
    Tries multiple PSM modes to handle different crop layouts.
    """
    # PSM modes to try:
    # 6 = Assume a single uniform block of text (often best for number regions)
    # 7 = Treat the image as a single text line
    # 13 = Raw line (no OSD or OCR)
    configs = [
        "--psm 6 -c tessedit_char_whitelist=0123456789/",
        "--psm 7 -c tessedit_char_whitelist=0123456789/",
        "--psm 13 -c tessedit_char_whitelist=0123456789/",
    ]
    
    all_text = []
    
    # Try on original crop first
    for config in configs:
        try:
            text = pytesseract.image_to_string(crop, lang=TESSERACT_LANG, config=config)
            text = (text or "").strip()
            if text:
                all_text.append(text)
                # Check if we found a valid number pattern
                number = _parse_card_number(text)
                if number and _is_plausible_card_number(number):
                    return text
        except Exception:
            continue
    
    # Try on preprocessed version
    try:
        processed = _preprocess_image(crop)
        for config in configs[:2]:  # Limit for speed
            try:
                text = pytesseract.image_to_string(processed, lang=TESSERACT_LANG, config=config)
                text = (text or "").strip()
                if text:
                    all_text.append(text)
                    number = _parse_card_number(text)
                    if number and _is_plausible_card_number(number):
                        return text
            except Exception:
                continue
    except Exception:
        pass
    
    # Return the longest text containing a slash
    slash_texts = [t for t in all_text if "/" in t]
    if slash_texts:
        return max(slash_texts, key=len)
    return all_text[0] if all_text else ""


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
    """Check if a card number is plausible for Pokemon TCG cards.
    
    Returns True for numbers that pass basic validation:
    - Format: X/Y where X and Y are 1-3 digit numbers
    - Total (Y) is between 10 and 500 (most sets are 50-300)
    - Number (X) is positive and not too far beyond total (secret rares)
    """
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
    # Minimum set size (smallest legitimate sets have ~10-20 cards)
    if total < 10:
        return False
    # Maximum set size (largest sets are ~300-400)
    if total > 500:
        return False
    # Secret rares can exceed total; allow a reasonable margin (~150 max)
    if num > total + 150:
        return False
    # Additional check: reject very small numbers with very large totals
    # (e.g., "1/999" is likely OCR noise)
    if total > 300 and num <= 10:
        # Could be valid, but less likely - don't reject but note as lower confidence
        pass
    return True


def _calculate_number_plausibility_score(card_number: str) -> float:
    """Calculate a plausibility score for a card number (0.0 to 1.0).
    
    Higher scores for more typical/common card number ranges.
    Modern sets commonly have secret rares that exceed the base total.
    """
    if not card_number:
        return 0.0
    m = CARD_NUMBER_PATTERN.search(card_number)
    if not m:
        return 0.0
    try:
        num = int(m.group(1))
        total = int(m.group(2))
    except ValueError:
        return 0.0
    
    score = 0.5  # Base score for valid format
    
    # Bonus for common set sizes (most sets are 100-250)
    if 100 <= total <= 250:
        score += 0.35
    elif 50 <= total <= 100 or 250 < total <= 350:
        score += 0.25
    elif 20 <= total <= 50:
        score += 0.15
    elif total < 20 or total > 400:
        score -= 0.2
    
    # Handle secret rares (number exceeds total)
    # Modern sets commonly have secret rares numbered above the base total
    if num <= total:
        score += 0.1  # Regular card
    elif num <= total + 30:
        score += 0.15  # Common secret rare range
    elif num <= total + 80:
        score += 0.10  # Extended secret rare (illustration rares, etc)
    elif num <= total + 150:
        score += 0.05  # Edge case secret rare
    else:
        score -= 0.15  # Unlikely
    
    return max(0.0, min(1.0, score))


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


def _number_regions_for_family(family: str) -> list[tuple[str, OCRRegion]]:
    """Return appropriate number regions based on template family.
    
    Different card templates have the collector number in different locations:
    - Modern/standard: usually bottom-left or bottom-right
    - Full art/special: often bottom-right with larger spacing
    - Vintage (WOTC era): bottom-right only, smaller region
    - Trainer cards: typically bottom-left
    """
    # Default: try all regions, prioritize bottom-right (most common)
    all_regions = [
        ("bottom_right:tight", CARD_NUMBER_BR_TIGHT),
        ("bottom_right:wide", CARD_NUMBER_BR_WIDE),
        ("bottom_left:tight", CARD_NUMBER_BL_TIGHT),
        ("bottom_left:wide", CARD_NUMBER_BL_WIDE),
    ]
    
    if family == "vintage":
        # WOTC era cards: number is typically bottom-right only
        return [
            ("bottom_right:tight", CARD_NUMBER_BR_TIGHT),
            ("bottom_right:wide", CARD_NUMBER_BR_WIDE),
        ]
    
    if family == "special":
        # Full art / holo cards: modern sets often use bottom-left
        # Prefer tight regions to avoid cutting off digits
        return [
            ("bottom_left:tight", CARD_NUMBER_BL_TIGHT),
            ("bottom_left:wide", CARD_NUMBER_BL_WIDE),
            ("bottom_right:tight", CARD_NUMBER_BR_TIGHT),
            ("bottom_right:wide", CARD_NUMBER_BR_WIDE),
        ]
    
    # Modern cards: standard order
    return all_regions


def _number_regions_for_card_type(card_type: str, family: str) -> list[tuple[str, OCRRegion]]:
    """Return appropriate number regions based on card type and template family.
    
    Card type influences where to look for the collector number:
    - Pokemon cards: typically bottom-right for modern, varies for vintage
    - Trainer cards: modern trainers often bottom-left, vintage bottom-right
    - Energy cards: basic energy may not have a number, special energy has number
    
    Args:
        card_type: Detected card type (pokemon, trainer, energy, unknown)
        family: Template family (modern, vintage, special)
        
    Returns:
        Ordered list of (label, region) tuples to try for number extraction
    """
    if card_type == "trainer":
        # Trainer cards: prefer bottom-left (modern design)
        # But also check bottom-right for older sets
        return [
            ("bottom_left:tight", CARD_NUMBER_BL_TIGHT),
            ("bottom_left:wide", CARD_NUMBER_BL_WIDE),
            ("bottom_right:tight", CARD_NUMBER_BR_TIGHT),
            ("bottom_right:wide", CARD_NUMBER_BR_WIDE),
        ]
    
    if card_type == "energy":
        # Energy cards: basic energy usually has number at bottom-left
        # Special energy varies, check both sides
        return [
            ("bottom_left:tight", CARD_NUMBER_BL_TIGHT),
            ("bottom_left:wide", CARD_NUMBER_BL_WIDE),
            ("bottom_right:tight", CARD_NUMBER_BR_TIGHT),
            ("bottom_right:wide", CARD_NUMBER_BR_WIDE),
        ]
    
    # Pokemon cards or unknown: use template family heuristics
    return _number_regions_for_family(family)


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
        match_method=f"ocr_extraction_failed:{content_hash[:16]}",
        card_type="unknown",
        trainer_subtype=None,
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
        match_method=f"ocr_extraction_failed:{path_hash[:16]}",
        card_type="unknown",
        trainer_subtype=None,
    )
