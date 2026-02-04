"""Tests for ConditionSignal generation from grading results.

These tests verify:
1. Signals are generated correctly from grading pipeline output
2. Severity labels map correctly from numeric scores
3. Observations and evidence are human-readable
"""

import pytest
from PIL import Image

from domain.types import ConditionSignal
from services.grading.signals import (
    generate_condition_signals,
    _severity_label,
    SEVERITY_MINOR,
    SEVERITY_MODERATE,
    SEVERITY_SIGNIFICANT,
)
from services.grading.types import (
    GradeResult,
    GradeDistribution,
    CenteringResult,
    DefectSignals,
    PhotoQuality,
)


# ---------------------------------------------------------------------------
# Severity label mapping tests
# ---------------------------------------------------------------------------


class TestSeverityLabels:
    """Tests for severity score to label mapping."""
    
    def test_none_severity(self):
        """Scores below SEVERITY_MINOR should be 'none'."""
        assert _severity_label(0.0) == "none"
        assert _severity_label(0.1) == "none"
        assert _severity_label(SEVERITY_MINOR - 0.01) == "none"
    
    def test_minor_severity(self):
        """Scores at or above SEVERITY_MINOR but below MODERATE should be 'minor'."""
        assert _severity_label(SEVERITY_MINOR) == "minor"
        assert _severity_label(0.35) == "minor"
        assert _severity_label(SEVERITY_MODERATE - 0.01) == "minor"
    
    def test_moderate_severity(self):
        """Scores at or above SEVERITY_MODERATE but below SIGNIFICANT should be 'moderate'."""
        assert _severity_label(SEVERITY_MODERATE) == "moderate"
        assert _severity_label(0.6) == "moderate"
        assert _severity_label(SEVERITY_SIGNIFICANT - 0.01) == "moderate"
    
    def test_significant_severity(self):
        """Scores at or above SEVERITY_SIGNIFICANT should be 'significant'."""
        assert _severity_label(SEVERITY_SIGNIFICANT) == "significant"
        assert _severity_label(0.9) == "significant"
        assert _severity_label(1.0) == "significant"


# ---------------------------------------------------------------------------
# ConditionSignal generation tests
# ---------------------------------------------------------------------------


def _make_test_grade_result(
    centering_psa_max: int = 10,
    centering_lr: float = 50.5,
    centering_tb: float = 51.0,
    corners_severity: float = 0.1,
    edges_severity: float = 0.1,
    surface_severity: float = 0.1,
) -> GradeResult:
    """Create a test GradeResult with configurable parameters."""
    return GradeResult(
        grade_distribution=GradeDistribution(p7=0.05, p8=0.15, p9=0.40, p10=0.40),
        expected_grade=9.15,
        p_psa10=0.40,
        confidence=0.85,
        centering=CenteringResult(
            lr_ratio=centering_lr,
            tb_ratio=centering_tb,
            psa_max=centering_psa_max,
            score=0.95,
            details={
                "front_detected": True,
                "back_detected": True,
                "back_method": "inner_rect",
            },
        ),
        defects=DefectSignals(
            corners_severity=corners_severity,
            edges_severity=edges_severity,
            surface_severity=surface_severity,
            details={
                "corners": {
                    "per_corner_summary": {
                        "top_left": {"whitening_ratio": 0.02, "severity": corners_severity * 0.8},
                        "top_right": {"whitening_ratio": 0.01, "severity": corners_severity * 0.5},
                        "bottom_left": {"whitening_ratio": 0.03, "severity": corners_severity},
                        "bottom_right": {"whitening_ratio": 0.01, "severity": corners_severity * 0.6},
                    },
                },
                "edges": {
                    "per_edge_summary": {
                        "top": {"whitening_ratio": 0.01, "chipping_score": 0.1, "severity": edges_severity * 0.8},
                        "bottom": {"whitening_ratio": 0.02, "chipping_score": 0.15, "severity": edges_severity},
                        "left": {"whitening_ratio": 0.01, "chipping_score": 0.08, "severity": edges_severity * 0.6},
                        "right": {"whitening_ratio": 0.01, "chipping_score": 0.1, "severity": edges_severity * 0.7},
                    },
                },
                "surface": {
                    "scratch_count": 2,
                    "texture_variance": 8.5,
                },
            },
        ),
        photo_quality=PhotoQuality(
            blur=0.1,
            glare=0.05,
            occlusion=0.02,
            usable=True,
            reasons=(),
        ),
        explanations={},
        trace={},
    )


class TestConditionSignalGeneration:
    """Tests for ConditionSignal generation from GradeResult."""
    
    def test_generates_four_signals(self):
        """Should generate signals for centering, corners, edges, surface."""
        result = _make_test_grade_result()
        signals = generate_condition_signals(result)
        
        assert len(signals) == 4
        signal_types = {s.signal_type for s in signals}
        assert signal_types == {"centering", "corners", "edges", "surface"}
    
    def test_all_signals_are_condition_signal_type(self):
        """All generated signals should be ConditionSignal instances."""
        result = _make_test_grade_result()
        signals = generate_condition_signals(result)
        
        for signal in signals:
            assert isinstance(signal, ConditionSignal)
    
    def test_signals_have_required_fields(self):
        """Each signal should have all required fields populated."""
        result = _make_test_grade_result()
        signals = generate_condition_signals(result)
        
        for signal in signals:
            assert signal.signal_type in ("centering", "corners", "edges", "surface")
            assert isinstance(signal.observation, str)
            assert len(signal.observation) > 0
            assert signal.severity in ("none", "minor", "moderate", "significant")
            assert 0.0 <= signal.confidence <= 1.0
            assert isinstance(signal.evidence_description, str)
            assert len(signal.evidence_description) > 0
    
    def test_centering_signal_reflects_psa_max(self):
        """Centering signal severity should reflect PSA max grade."""
        # PSA 10 centering -> none severity
        result_10 = _make_test_grade_result(centering_psa_max=10)
        signals_10 = generate_condition_signals(result_10)
        centering_10 = next(s for s in signals_10 if s.signal_type == "centering")
        assert centering_10.severity == "none"
        
        # PSA 8 centering -> minor severity
        result_8 = _make_test_grade_result(centering_psa_max=8)
        signals_8 = generate_condition_signals(result_8)
        centering_8 = next(s for s in signals_8 if s.signal_type == "centering")
        assert centering_8.severity == "minor"
        
        # PSA 6 centering -> significant severity
        result_6 = _make_test_grade_result(centering_psa_max=6)
        signals_6 = generate_condition_signals(result_6)
        centering_6 = next(s for s in signals_6 if s.signal_type == "centering")
        assert centering_6.severity == "significant"
    
    def test_defect_signals_reflect_severity(self):
        """Defect signals should reflect input severity scores."""
        # Low severity defects -> none
        result_low = _make_test_grade_result(corners_severity=0.1, edges_severity=0.1, surface_severity=0.1)
        signals_low = generate_condition_signals(result_low)
        
        corners_low = next(s for s in signals_low if s.signal_type == "corners")
        edges_low = next(s for s in signals_low if s.signal_type == "edges")
        surface_low = next(s for s in signals_low if s.signal_type == "surface")
        
        assert corners_low.severity == "none"
        assert edges_low.severity == "none"
        assert surface_low.severity == "none"
        
        # High severity defects -> significant
        result_high = _make_test_grade_result(corners_severity=0.8, edges_severity=0.8, surface_severity=0.8)
        signals_high = generate_condition_signals(result_high)
        
        corners_high = next(s for s in signals_high if s.signal_type == "corners")
        edges_high = next(s for s in signals_high if s.signal_type == "edges")
        surface_high = next(s for s in signals_high if s.signal_type == "surface")
        
        assert corners_high.severity == "significant"
        assert edges_high.severity == "significant"
        assert surface_high.severity == "significant"
    
    def test_observations_are_human_readable(self):
        """Observations should be human-readable sentences."""
        result = _make_test_grade_result()
        signals = generate_condition_signals(result)
        
        for signal in signals:
            # Check it's not a technical dump
            assert not signal.observation.startswith("{")
            assert not signal.observation.startswith("[")
            # Check it has proper sentence structure (starts with capital, reasonable length)
            assert signal.observation[0].isupper() or signal.observation[0].isdigit()
            assert len(signal.observation) >= 20  # Not too short
    
    def test_evidence_includes_measurements(self):
        """Evidence descriptions should include actual measurements."""
        result = _make_test_grade_result(centering_lr=55.2, centering_tb=52.3)
        signals = generate_condition_signals(result)
        
        centering = next(s for s in signals if s.signal_type == "centering")
        # Should mention the ratio values
        assert "55.2" in centering.evidence_description or "ratio" in centering.evidence_description.lower()
    
    def test_signals_are_immutable(self):
        """Generated signals should be frozen dataclasses."""
        result = _make_test_grade_result()
        signals = generate_condition_signals(result)
        
        for signal in signals:
            with pytest.raises((TypeError, AttributeError)):
                signal.severity = "modified"  # type: ignore


class TestSignalDeterminism:
    """Tests to verify signal generation is deterministic."""
    
    def test_same_input_same_output(self):
        """Same GradeResult should produce identical signals."""
        result = _make_test_grade_result()
        
        signals1 = generate_condition_signals(result)
        signals2 = generate_condition_signals(result)
        
        assert len(signals1) == len(signals2)
        
        for s1, s2 in zip(signals1, signals2):
            assert s1.signal_type == s2.signal_type
            assert s1.observation == s2.observation
            assert s1.severity == s2.severity
            assert s1.confidence == s2.confidence
            assert s1.evidence_description == s2.evidence_description
