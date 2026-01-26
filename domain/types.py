"""
PreGrade Core Domain Types

These types define the data structures used across the PreGrade system.
All types are JSON-serialisable and designed for AWS Lambda responses.

IMPORTANT: These types represent advisory, probabilistic outputs.
PreGrade does NOT assign grades or act as an authority.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
import json


@dataclass(frozen=True)
class CardIdentity:
    """
    Identifies a trading card from image analysis.
    
    This represents the system's best identification of the card,
    along with confidence and traceability information.
    """
    
    set_name: str
    """The name of the card set (e.g., 'Base Set', 'Evolving Skies')."""
    
    card_name: str
    """The name of the card (e.g., 'Charizard', 'Pikachu')."""
    
    card_number: Optional[str]
    """The card number within the set, if available."""
    
    variant: Optional[str]
    """Card variant if applicable (e.g., 'Holo', 'Reverse Holo', '1st Edition')."""
    
    confidence: float
    """Confidence score for this identification (0.0 to 1.0)."""
    
    match_method: str
    """Description of how the card was identified (for traceability)."""

    def to_dict(self) -> dict:
        """Convert to JSON-serialisable dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class ConditionSignal:
    """
    A single condition observation from image analysis.
    
    IMPORTANT: This is NOT a grade. It is an advisory signal describing
    an observed condition characteristic with supporting evidence.
    """
    
    signal_type: str
    """
    The type of condition signal observed.
    Examples: 'centering', 'surface', 'corners', 'edges', 'print_quality'.
    """
    
    observation: str
    """Human-readable description of what was observed."""
    
    severity: str
    """
    Advisory severity level of the observation.
    Values: 'none', 'minor', 'moderate', 'significant'.
    """
    
    confidence: float
    """Confidence score for this observation (0.0 to 1.0)."""
    
    evidence_description: str
    """Description of the visual evidence supporting this signal."""

    def to_dict(self) -> dict:
        """Convert to JSON-serialisable dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class GatekeeperResult:
    """
    The result of the gatekeeper evaluation.
    
    The gatekeeper determines whether analysis can proceed or should be
    rejected. Rejections are valid, expected, and billable outcomes.
    
    A rejection is NOT a failure - it is a confident determination that
    analysis cannot proceed for specific, explainable reasons.
    """
    
    accepted: bool
    """Whether the submission passed the gatekeeper."""
    
    reason_codes: tuple[str, ...]
    """
    Machine-readable codes explaining the decision.
    Empty tuple if accepted.
    Examples: 'IMAGE_QUALITY_INSUFFICIENT', 'CARD_NOT_VISIBLE', 'MULTIPLE_CARDS_DETECTED'.
    """
    
    reasons: tuple[str, ...]
    """
    Human-readable explanations for each reason code.
    Empty tuple if accepted.
    """
    
    explanation: str
    """Overall human-readable explanation of the gatekeeper decision."""

    def to_dict(self) -> dict:
        """Convert to JSON-serialisable dictionary."""
        result = asdict(self)
        result['reason_codes'] = list(self.reason_codes)
        result['reasons'] = list(self.reasons)
        return result


@dataclass(frozen=True)
class ROIResult:
    """
    ROI-based recommendation on whether grading is advisable.
    
    IMPORTANT: This is advisory only. It represents a data-driven
    recommendation based on condition signals and market context,
    NOT a guarantee of outcome or value.
    """
    
    recommendation: str
    """
    The advisory recommendation.
    Values: 'recommended', 'not_recommended', 'uncertain'.
    """
    
    risk_band: str
    """
    Advisory risk categorisation.
    Values: 'low', 'medium', 'high'.
    """
    
    confidence: float
    """Confidence score for this recommendation (0.0 to 1.0)."""
    
    factors: tuple[str, ...]
    """List of factors that influenced this recommendation."""
    
    explanation: str
    """Human-readable explanation of the recommendation rationale."""

    def to_dict(self) -> dict:
        """Convert to JSON-serialisable dictionary."""
        result = asdict(self)
        result['factors'] = list(self.factors)
        return result


@dataclass(frozen=True)
class AnalysisResult:
    """
    The complete result of a PreGrade analysis.
    
    This is the top-level response type returned by the API.
    It combines card identification, condition signals, gatekeeper
    decision, and ROI recommendation with full explainability.
    """
    
    request_id: str
    """Unique identifier for this analysis request (for traceability)."""
    
    card_identity: Optional[CardIdentity]
    """
    The identified card, if identification succeeded.
    None if the card could not be identified.
    """
    
    condition_signals: tuple[ConditionSignal, ...]
    """
    Condition signals observed during analysis.
    May be empty if gatekeeper rejected before condition analysis.
    """
    
    gatekeeper_result: GatekeeperResult
    """The gatekeeper evaluation result."""
    
    roi_result: Optional[ROIResult]
    """
    The ROI recommendation, if analysis proceeded.
    None if gatekeeper rejected the submission.
    """
    
    processed_at: str
    """ISO 8601 timestamp of when analysis was completed."""

    def to_dict(self) -> dict:
        """Convert to JSON-serialisable dictionary."""
        return {
            'request_id': self.request_id,
            'card_identity': self.card_identity.to_dict() if self.card_identity else None,
            'condition_signals': [s.to_dict() for s in self.condition_signals],
            'gatekeeper_result': self.gatekeeper_result.to_dict(),
            'roi_result': self.roi_result.to_dict() if self.roi_result else None,
            'processed_at': self.processed_at,
        }

    def to_json(self) -> str:
        """Serialise to JSON string."""
        return json.dumps(self.to_dict())
