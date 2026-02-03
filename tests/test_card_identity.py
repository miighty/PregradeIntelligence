"""
Tests for Card Identity Detection Service

Validates: determinism, output stability, graceful error handling.
"""

import io
import pytest
from PIL import Image
import numpy as np

from services.card_identity import (
    extract_card_identity,
    extract_card_identity_from_bytes,
    extract_card_identity_from_path,
    _compute_image_hash,
    _parse_card_name,
    _parse_card_number,
    _calculate_confidence,
    _preprocess_image,
    _is_likely_pokemon_name,
    _score_name_candidate,
    _is_plausible_card_number,
    _calculate_number_plausibility_score,
)
from domain.types import CardIdentity


def _create_test_image(width: int = 400, height: int = 560, seed: int = 42) -> Image.Image:
    """Create a deterministic test image."""
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 256, (height, width, 3), dtype=np.uint8)
    return Image.fromarray(arr, mode='RGB')


def _image_to_bytes(image: Image.Image, format: str = 'PNG') -> bytes:
    """Convert PIL Image to bytes."""
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    return buffer.getvalue()


class TestDeterminism:
    """Verify same input produces same output."""
    
    def test_identical_images_produce_identical_hash(self):
        img1 = _create_test_image(seed=100)
        img2 = _create_test_image(seed=100)
        
        hash1 = _compute_image_hash(img1)
        hash2 = _compute_image_hash(img2)
        
        assert hash1 == hash2
    
    def test_different_images_produce_different_hash(self):
        img1 = _create_test_image(seed=100)
        img2 = _create_test_image(seed=200)
        
        hash1 = _compute_image_hash(img1)
        hash2 = _compute_image_hash(img2)
        
        assert hash1 != hash2
    
    def test_extract_card_identity_is_deterministic(self):
        img = _create_test_image(seed=42)
        
        result1 = extract_card_identity(img)
        result2 = extract_card_identity(img)
        
        assert result1.card_name == result2.card_name
        assert result1.set_name == result2.set_name
        assert result1.card_number == result2.card_number
        assert result1.confidence == result2.confidence
        assert result1.match_method == result2.match_method


class TestOutputStructure:
    """Verify CardIdentity output has correct structure."""
    
    def test_returns_card_identity_type(self):
        img = _create_test_image()
        result = extract_card_identity(img)
        
        assert isinstance(result, CardIdentity)
    
    def test_has_required_fields(self):
        img = _create_test_image()
        result = extract_card_identity(img)
        
        assert hasattr(result, 'card_name')
        assert hasattr(result, 'set_name')
        assert hasattr(result, 'card_number')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'match_method')
    
    def test_confidence_is_numeric(self):
        img = _create_test_image()
        result = extract_card_identity(img)
        
        assert isinstance(result.confidence, float)
        assert 0.0 <= result.confidence <= 1.0
    
    def test_match_method_contains_hash(self):
        img = _create_test_image()
        result = extract_card_identity(img)
        
        assert result.match_method.startswith('ocr_extraction:')
        assert len(result.match_method) > len('ocr_extraction:')


class TestGracefulErrorHandling:
    """Verify no exceptions raised, low confidence returned instead."""
    
    def test_invalid_bytes_returns_zero_confidence(self):
        invalid_bytes = b'not an image'
        result = extract_card_identity_from_bytes(invalid_bytes)
        
        assert isinstance(result, CardIdentity)
        assert result.confidence == 0.0
        assert 'failed' in result.match_method
    
    def test_nonexistent_path_returns_zero_confidence(self):
        result = extract_card_identity_from_path('/nonexistent/path/image.png')
        
        assert isinstance(result, CardIdentity)
        assert result.confidence == 0.0
        assert 'failed' in result.match_method
    
    def test_empty_bytes_returns_zero_confidence(self):
        result = extract_card_identity_from_bytes(b'')
        
        assert isinstance(result, CardIdentity)
        assert result.confidence == 0.0


class TestParsing:
    """Verify parsing functions behave correctly."""
    
    def test_parse_card_name_empty_input(self):
        assert _parse_card_name('') == ''
        assert _parse_card_name(None) == ''
    
    def test_parse_card_name_removes_invalid_chars(self):
        result = _parse_card_name('Pikachu123!')
        assert result == 'Pikachu'
    
    def test_parse_card_name_preserves_spaces(self):
        result = _parse_card_name('Dark Charizard')
        assert result == 'Dark Charizard'
    
    def test_parse_card_name_preserves_accents(self):
        result = _parse_card_name('Pokémon')
        assert 'Pok' in result
    
    def test_parse_card_number_valid_format(self):
        assert _parse_card_number('4/102') == '4/102'
        assert _parse_card_number('04/102') == '4/102'
        assert _parse_card_number('004/102') == '4/102'
    
    def test_parse_card_number_with_surrounding_text(self):
        assert _parse_card_number('Card 4/102 Base') == '4/102'
    
    def test_parse_card_number_no_match(self):
        assert _parse_card_number('no number here') is None
        assert _parse_card_number('') is None
        assert _parse_card_number(None) is None


class TestConfidenceCalculation:
    """Verify confidence scoring is explicit and correct."""
    
    def test_full_confidence_all_fields(self):
        confidence = _calculate_confidence(
            card_name='Charizard',
            card_number='4/102'
        )
        assert confidence == 1.0
    
    def test_zero_confidence_no_fields(self):
        confidence = _calculate_confidence(
            card_name='',
            card_number=None
        )
        assert confidence == 0.0
    
    def test_partial_confidence_name_only(self):
        confidence = _calculate_confidence(
            card_name='Charizard',
            card_number=None
        )
        assert confidence == 0.5
    
    def test_partial_confidence_number_only(self):
        confidence = _calculate_confidence(
            card_name='',
            card_number='4/102'
        )
        assert confidence == 0.5
    
    def test_short_name_reduced_confidence(self):
        confidence = _calculate_confidence(
            card_name='AB',
            card_number=None
        )
        assert confidence == 0.2
    
    def test_confidence_is_rounded(self):
        confidence = _calculate_confidence(
            card_name='Charizard',
            card_number='4/102'
        )
        assert confidence == round(confidence, 2)


class TestPreprocessing:
    """Verify image preprocessing is deterministic."""
    
    def test_preprocessing_is_deterministic(self):
        img = _create_test_image(seed=42)
        
        result1 = _preprocess_image(img)
        result2 = _preprocess_image(img)
        
        arr1 = np.array(result1)
        arr2 = np.array(result2)
        
        assert np.array_equal(arr1, arr2)
    
    def test_preprocessing_converts_to_grayscale(self):
        img = _create_test_image()
        result = _preprocess_image(img)
        
        assert result.mode == 'L'


class TestFromBytes:
    """Verify bytes-based extraction works correctly."""
    
    def test_valid_png_bytes(self):
        img = _create_test_image()
        img_bytes = _image_to_bytes(img, 'PNG')
        
        result = extract_card_identity_from_bytes(img_bytes)
        
        assert isinstance(result, CardIdentity)
    
    def test_valid_jpeg_bytes(self):
        img = _create_test_image().convert('RGB')
        img_bytes = _image_to_bytes(img, 'JPEG')
        
        result = extract_card_identity_from_bytes(img_bytes)
        
        assert isinstance(result, CardIdentity)
    
    def test_bytes_extraction_matches_direct(self):
        img = _create_test_image(seed=99)
        img_bytes = _image_to_bytes(img, 'PNG')
        
        direct_result = extract_card_identity(img)
        bytes_result = extract_card_identity_from_bytes(img_bytes)
        
        assert direct_result.confidence == bytes_result.confidence


class TestSerialization:
    """Verify CardIdentity serializes correctly."""
    
    def test_to_dict_returns_dict(self):
        img = _create_test_image()
        result = extract_card_identity(img)
        
        as_dict = result.to_dict()
        
        assert isinstance(as_dict, dict)
        assert 'card_name' in as_dict
        assert 'set_name' in as_dict
        assert 'card_number' in as_dict
        assert 'confidence' in as_dict
        assert 'match_method' in as_dict


class TestPokemonNameValidation:
    """Verify Pokemon name validation logic."""
    
    def test_recognizes_common_pokemon(self):
        assert _is_likely_pokemon_name('Pikachu')
        assert _is_likely_pokemon_name('Charizard')
        assert _is_likely_pokemon_name('Mewtwo')
        assert _is_likely_pokemon_name('Gengar')
    
    def test_recognizes_case_insensitive(self):
        assert _is_likely_pokemon_name('pikachu')
        assert _is_likely_pokemon_name('CHARIZARD')
        assert _is_likely_pokemon_name('MeWtWo')
    
    def test_rejects_garbage(self):
        assert not _is_likely_pokemon_name('xyz')
        assert not _is_likely_pokemon_name('a')
        assert not _is_likely_pokemon_name('')
        assert not _is_likely_pokemon_name('asdfgh')
    
    def test_recognizes_modifiers(self):
        assert _is_likely_pokemon_name('Dark')
        assert _is_likely_pokemon_name('ex')
        assert _is_likely_pokemon_name('GX')
    
    def test_substring_matching(self):
        # Should match if known name is substring
        assert _is_likely_pokemon_name('Pikachu EX')
        assert _is_likely_pokemon_name('Dark Charizard')


class TestNameScoring:
    """Verify name candidate scoring."""
    
    def test_pokemon_name_scores_higher(self):
        score_pokemon = _score_name_candidate('Pikachu')
        score_garbage = _score_name_candidate('xyz')
        assert score_pokemon > score_garbage
    
    def test_multi_word_pokemon_scores_higher(self):
        score_multi = _score_name_candidate('Dark Charizard')
        score_single_modifier = _score_name_candidate('Dark')
        assert score_multi > score_single_modifier
    
    def test_empty_string_scores_zero(self):
        assert _score_name_candidate('') == 0.0
    
    def test_reasonable_length_preferred(self):
        score_good = _score_name_candidate('Pikachu')
        score_too_long = _score_name_candidate('A' * 50)
        assert score_good > score_too_long


class TestCardNumberPlausibility:
    """Verify card number plausibility checks."""
    
    def test_valid_numbers(self):
        assert _is_plausible_card_number('1/100')
        assert _is_plausible_card_number('50/200')
        assert _is_plausible_card_number('100/100')
    
    def test_secret_rares_valid(self):
        # Secret rares can exceed total
        assert _is_plausible_card_number('110/100')
        assert _is_plausible_card_number('200/150')
    
    def test_rejects_impossible(self):
        # Number way beyond total
        assert not _is_plausible_card_number('500/100')
        # Total too small
        assert not _is_plausible_card_number('1/5')
        # Total too large
        assert not _is_plausible_card_number('1/999')
    
    def test_rejects_invalid_format(self):
        assert not _is_plausible_card_number('')
        assert not _is_plausible_card_number('abc')
        assert not _is_plausible_card_number('100')
    
    def test_plausibility_score_higher_for_common_ranges(self):
        # Common set size should score higher
        score_common = _calculate_number_plausibility_score('50/100')
        score_uncommon = _calculate_number_plausibility_score('50/400')
        assert score_common > score_uncommon
    
    def test_plausibility_score_within_bounds(self):
        score = _calculate_number_plausibility_score('50/100')
        assert 0.0 <= score <= 1.0


class TestImprovedNameParsing:
    """Verify improved name parsing handles various inputs."""
    
    def test_strips_hp_values(self):
        result = _parse_card_name('Pikachu HP 60')
        assert 'HP' not in result.upper()
        assert 'Pikachu' in result
    
    def test_strips_trainer_noise(self):
        result = _parse_card_name('Trainer Put 2 damage')
        # Should strip noise tokens
        assert 'damage' not in result.lower()
    
    def test_handles_multi_word_names(self):
        result = _parse_card_name('Dark Charizard something else')
        assert 'Dark' in result
        assert 'Charizard' in result
    
    def test_prefers_validated_names(self):
        # Input with valid Pokemon name should be extracted
        result = _parse_card_name('Pikachu')
        assert result == 'Pikachu'
