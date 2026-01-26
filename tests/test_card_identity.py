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
    _parse_set_name,
    _calculate_confidence,
    _preprocess_image,
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
    
    def test_parse_set_name_empty_input(self):
        assert _parse_set_name('') == 'Unknown Set'
        assert _parse_set_name(None) == 'Unknown Set'
    
    def test_parse_set_name_filters_numbers(self):
        result = _parse_set_name('4/102 Base Set')
        assert 'Base Set' in result


class TestConfidenceCalculation:
    """Verify confidence scoring is explicit and correct."""
    
    def test_full_confidence_all_fields(self):
        confidence = _calculate_confidence(
            card_name='Charizard',
            card_number='4/102',
            set_name='Base Set'
        )
        assert confidence == 1.0
    
    def test_zero_confidence_no_fields(self):
        confidence = _calculate_confidence(
            card_name='',
            card_number=None,
            set_name='Unknown Set'
        )
        assert confidence == 0.0
    
    def test_partial_confidence_name_only(self):
        confidence = _calculate_confidence(
            card_name='Charizard',
            card_number=None,
            set_name='Unknown Set'
        )
        assert confidence == 0.4
    
    def test_partial_confidence_number_only(self):
        confidence = _calculate_confidence(
            card_name='',
            card_number='4/102',
            set_name='Unknown Set'
        )
        assert confidence == 0.35
    
    def test_short_name_reduced_confidence(self):
        confidence = _calculate_confidence(
            card_name='AB',
            card_number=None,
            set_name='Unknown Set'
        )
        assert confidence == 0.15
    
    def test_confidence_is_rounded(self):
        confidence = _calculate_confidence(
            card_name='Charizard',
            card_number='4/102',
            set_name='Unknown Set'
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
