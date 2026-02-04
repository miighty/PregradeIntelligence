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
    _extract_name_components,
    _validate_base_pokemon_name,
    _reconstruct_card_name,
    _detect_card_type_from_text,
    _detect_trainer_subtype,
)
from domain.types import CardIdentity, CardType, TrainerSubtype


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


class TestNameComponentExtraction:
    """Verify prefix/suffix extraction from card names."""
    
    def test_simple_pokemon_name(self):
        prefixes, base, suffixes = _extract_name_components('Pikachu')
        assert prefixes == []
        assert base == 'pikachu'
        assert suffixes == []
    
    def test_dark_prefix(self):
        prefixes, base, suffixes = _extract_name_components('Dark Charizard')
        assert 'dark' in prefixes
        assert base == 'charizard'
        assert suffixes == []
    
    def test_owner_prefix(self):
        prefixes, base, suffixes = _extract_name_components("Brock's Onix")
        assert any("brock" in p for p in prefixes)
        assert 'onix' in base.lower()
    
    def test_team_rocket_prefix(self):
        prefixes, base, suffixes = _extract_name_components("Team Rocket's Mewtwo")
        assert any("rocket" in p for p in prefixes)
        assert 'mewtwo' in base.lower()
    
    def test_mechanic_suffix_ex(self):
        prefixes, base, suffixes = _extract_name_components('Pikachu ex')
        assert prefixes == []
        assert base == 'pikachu'
        assert 'ex' in suffixes
    
    def test_mechanic_suffix_vmax(self):
        prefixes, base, suffixes = _extract_name_components('Charizard VMAX')
        assert base == 'charizard'
        assert 'vmax' in suffixes
    
    def test_combined_prefix_and_suffix(self):
        prefixes, base, suffixes = _extract_name_components('Dark Alakazam ex')
        assert 'dark' in prefixes
        assert 'alakazam' in base.lower()
        assert 'ex' in suffixes
    
    def test_regional_form_prefix(self):
        prefixes, base, suffixes = _extract_name_components('Alolan Ninetales GX')
        assert 'alolan' in prefixes
        assert 'ninetales' in base.lower()
        assert 'gx' in suffixes
    
    def test_galarian_form(self):
        prefixes, base, suffixes = _extract_name_components('Galarian Rapidash')
        assert 'galarian' in prefixes
        assert 'rapidash' in base.lower()


class TestBasePokemonNameValidation:
    """Verify base Pokemon name validation."""
    
    def test_gen1_pokemon(self):
        assert _validate_base_pokemon_name('pikachu')
        assert _validate_base_pokemon_name('charizard')
        assert _validate_base_pokemon_name('mewtwo')
    
    def test_gen2_pokemon(self):
        assert _validate_base_pokemon_name('typhlosion')
        assert _validate_base_pokemon_name('lugia')
        assert _validate_base_pokemon_name('celebi')
    
    def test_gen3_pokemon(self):
        assert _validate_base_pokemon_name('blaziken')
        assert _validate_base_pokemon_name('rayquaza')
        assert _validate_base_pokemon_name('deoxys')
    
    def test_gen4_pokemon(self):
        assert _validate_base_pokemon_name('lucario')
        assert _validate_base_pokemon_name('garchomp')
        assert _validate_base_pokemon_name('arceus')
    
    def test_gen5_pokemon(self):
        assert _validate_base_pokemon_name('zoroark')
        assert _validate_base_pokemon_name('hydreigon')
        assert _validate_base_pokemon_name('reshiram')
    
    def test_gen6_pokemon(self):
        assert _validate_base_pokemon_name('greninja')
        assert _validate_base_pokemon_name('xerneas')
        assert _validate_base_pokemon_name('sylveon')
    
    def test_gen7_pokemon(self):
        assert _validate_base_pokemon_name('decidueye')
        assert _validate_base_pokemon_name('mimikyu')
        assert _validate_base_pokemon_name('necrozma')
    
    def test_gen8_pokemon(self):
        assert _validate_base_pokemon_name('dragapult')
        assert _validate_base_pokemon_name('zacian')
        assert _validate_base_pokemon_name('eternatus')
    
    def test_gen9_pokemon(self):
        assert _validate_base_pokemon_name('meowscarada')
        assert _validate_base_pokemon_name('koraidon')
        assert _validate_base_pokemon_name('miraidon')
    
    def test_rejects_non_pokemon(self):
        assert not _validate_base_pokemon_name('asdfgh')
        assert not _validate_base_pokemon_name('')
        assert not _validate_base_pokemon_name('xyz')


class TestNameReconstruction:
    """Verify card name reconstruction from components."""
    
    def test_simple_name(self):
        result = _reconstruct_card_name([], 'pikachu', [])
        assert result == 'Pikachu'
    
    def test_with_prefix(self):
        result = _reconstruct_card_name(['dark'], 'charizard', [])
        assert result == 'Dark Charizard'
    
    def test_with_suffix(self):
        result = _reconstruct_card_name([], 'pikachu', ['ex'])
        assert 'Pikachu' in result
        assert 'EX' in result.upper()
    
    def test_with_prefix_and_suffix(self):
        result = _reconstruct_card_name(['dark'], 'alakazam', ['ex'])
        assert 'Dark' in result
        assert 'Alakazam' in result
        assert 'EX' in result.upper()
    
    def test_vmax_formatting(self):
        result = _reconstruct_card_name([], 'charizard', ['vmax'])
        assert 'VMAX' in result


class TestLongNameParsing:
    """Verify handling of longer card names."""
    
    def test_parses_dark_charizard(self):
        result = _parse_card_name('Dark Charizard')
        assert 'Dark' in result
        assert 'Charizard' in result
    
    def test_parses_team_rocket_mewtwo(self):
        result = _parse_card_name("Team Rocket's Mewtwo")
        assert 'Mewtwo' in result
    
    def test_parses_alolan_ninetales_gx(self):
        result = _parse_card_name('Alolan Ninetales GX')
        assert 'Ninetales' in result
    
    def test_handles_name_up_to_50_chars(self):
        long_name = 'A' * 45
        result = _parse_card_name(long_name)
        # Should not crash, even if not a valid Pokemon
        assert isinstance(result, str)
    
    def test_validates_complex_names(self):
        # Complex names should be recognized as valid
        assert _is_likely_pokemon_name('Dark Charizard')
        assert _is_likely_pokemon_name("Team Rocket's Mewtwo")
        assert _is_likely_pokemon_name('Alolan Ninetales GX')
        assert _is_likely_pokemon_name('Pikachu VMAX')


class TestExpandedPokemonNameValidation:
    """Verify Pokemon name validation for all generations and variants."""
    
    def test_recognizes_gen3_pokemon(self):
        assert _is_likely_pokemon_name('Blaziken')
        assert _is_likely_pokemon_name('Rayquaza')
        assert _is_likely_pokemon_name('Metagross')
    
    def test_recognizes_gen9_pokemon(self):
        assert _is_likely_pokemon_name('Meowscarada')
        assert _is_likely_pokemon_name('Koraidon')
        assert _is_likely_pokemon_name('Miraidon')
    
    def test_recognizes_owner_prefixed_names(self):
        assert _is_likely_pokemon_name("Brock's Onix")
        assert _is_likely_pokemon_name("Misty's Tentacruel")
        assert _is_likely_pokemon_name("Blaine's Arcanine")
    
    def test_recognizes_variant_prefixed_names(self):
        assert _is_likely_pokemon_name('Dark Charizard')
        assert _is_likely_pokemon_name('Light Arcanine')
        assert _is_likely_pokemon_name('Shining Mew')
    
    def test_recognizes_regional_forms(self):
        assert _is_likely_pokemon_name('Alolan Ninetales')
        assert _is_likely_pokemon_name('Galarian Rapidash')
        assert _is_likely_pokemon_name('Hisuian Zoroark')
        assert _is_likely_pokemon_name('Paldean Tauros')
    
    def test_recognizes_mechanic_suffixes(self):
        assert _is_likely_pokemon_name('Charizard ex')
        assert _is_likely_pokemon_name('Pikachu VMAX')
        assert _is_likely_pokemon_name('Mewtwo GX')
        assert _is_likely_pokemon_name('Arceus VSTAR')


class TestCardTypeDetection:
    """Verify card type detection from OCR text."""
    
    def test_detects_trainer_card(self):
        assert _detect_card_type_from_text('TRAINER') == 'trainer'
        assert _detect_card_type_from_text('Trainer card text here') == 'trainer'
    
    def test_detects_supporter(self):
        assert _detect_card_type_from_text('Supporter') == 'trainer'
    
    def test_detects_stadium(self):
        assert _detect_card_type_from_text('Stadium') == 'trainer'
    
    def test_detects_energy_card(self):
        assert _detect_card_type_from_text('Basic Energy') == 'energy'
        assert _detect_card_type_from_text('Fire Energy') == 'energy'
    
    def test_detects_pokemon_card(self):
        # Cards with HP are Pokemon cards
        assert _detect_card_type_from_text('HP 120') == 'pokemon'
        assert _detect_card_type_from_text('Charizard 150 HP') == 'pokemon'
    
    def test_returns_unknown_for_empty(self):
        assert _detect_card_type_from_text('') == 'unknown'
        assert _detect_card_type_from_text(None) == 'unknown'


class TestTrainerSubtypeDetection:
    """Verify trainer subtype detection."""
    
    def test_detects_supporter(self):
        assert _detect_trainer_subtype('Supporter') == 'supporter'
        assert _detect_trainer_subtype('SUPPORTER card text') == 'supporter'
    
    def test_detects_stadium(self):
        assert _detect_trainer_subtype('Stadium') == 'stadium'
    
    def test_detects_item(self):
        assert _detect_trainer_subtype('Item') == 'item'
    
    def test_detects_pokemon_tool(self):
        assert _detect_trainer_subtype('Pokemon Tool') == 'pokemon_tool'
        assert _detect_trainer_subtype('Pokémon Tool') == 'pokemon_tool'
    
    def test_returns_none_for_unknown(self):
        assert _detect_trainer_subtype('') is None
        assert _detect_trainer_subtype('random text') is None


class TestCardIdentityStructure:
    """Verify CardIdentity includes new fields."""
    
    def test_card_identity_has_card_type(self):
        img = _create_test_image()
        result = extract_card_identity(img)
        assert hasattr(result, 'card_type')
        assert result.card_type in ['pokemon', 'trainer', 'energy', 'unknown']
    
    def test_card_identity_has_trainer_subtype(self):
        img = _create_test_image()
        result = extract_card_identity(img)
        assert hasattr(result, 'trainer_subtype')
    
    def test_card_identity_serializes_new_fields(self):
        img = _create_test_image()
        result = extract_card_identity(img)
        as_dict = result.to_dict()
        assert 'card_type' in as_dict
        assert 'trainer_subtype' in as_dict


class TestDomainEnums:
    """Verify domain enum definitions."""
    
    def test_card_type_enum_values(self):
        assert CardType.POKEMON.value == 'pokemon'
        assert CardType.TRAINER.value == 'trainer'
        assert CardType.ENERGY.value == 'energy'
        assert CardType.UNKNOWN.value == 'unknown'
    
    def test_trainer_subtype_enum_values(self):
        assert TrainerSubtype.ITEM.value == 'item'
        assert TrainerSubtype.SUPPORTER.value == 'supporter'
        assert TrainerSubtype.STADIUM.value == 'stadium'
        assert TrainerSubtype.POKEMON_TOOL.value == 'pokemon_tool'
