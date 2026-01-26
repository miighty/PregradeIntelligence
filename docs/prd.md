====================================
AUTHORITATIVE PRODUCT CONTEXT (FULL PRD)
====================================

PROJECT: PreGrade – Grading Intelligence API

PROBLEM:
Collectors, dealers, and portfolio apps lack reliable, data-driven answers to:
“Is this card worth grading?”

Grading fees are wasted on cards with poor ROI.
Dealers rely on gut feeling.
Portfolio apps track price but ignore condition and grading economics.

SOLUTION:
A backend decision-intelligence service that analyses trading card images and returns:
- Card identity
- Condition signals (not grades)
- Gatekeeper rejection / acceptance
- ROI-based grading recommendation
- Full explainability

THIS IS NOT A GRADER.

------------------------------------
NON-GOALS (CRITICAL)
------------------------------------
- No PSA/BGS grade assignment
- No population reports
- No price prediction claims
- No subjective scoring without explanation
- No consumer UI in this repository

------------------------------------
PRIMARY OUTPUTS
------------------------------------
- Deterministic JSON responses
- Explainable decision logic
- Structured rejection reasons
- ROI framing, not authority

------------------------------------
INITIAL CARD SCOPE
------------------------------------
- Pokémon cards only
- Modern + vintage
- Front image required
- Back image optional
- Images may include sleeves, glare, imperfect framing

------------------------------------
ARCHITECTURE CONSTRAINTS
------------------------------------
- Cloud: AWS
- Compute: Lambda-first
- API: REST
- Auth: API keys
- Storage: S3
- Language: Choose a sensible backend language and justify briefly

------------------------------------
CORE DOMAIN ENTITIES
------------------------------------
- CardIdentity
- ConditionSignal
- GatekeeperResult
- ROIResult
- AnalysisResult

------------------------------------
BUSINESS RULES
------------------------------------
- Gatekeeper rejections are valid outcomes
- Gatekeeper rejections are billable
- Same input must produce same output
- Every decision must include reason codes
- Explainability is a first-class requirement

