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

------------------------------------
PARTNER / PORTFOLIO-APP FOCUS (GO-TO-MARKET)
------------------------------------
Primary initial customer: **Portfolio / collection apps** (already have user photos).

Initial product promise (v1):
- Stable, partner-friendly endpoints
- Deterministic, explainable outputs
- Gatekeeper is a *feature* (fast verdict + structured rejection reasons)

Time horizon:
- Intend to compete in this market for **5+ years**, but validate demand quickly via pilot integrations.

------------------------------------
API UX: IMAGE UPLOADS (PARTNER-FRIENDLY)
------------------------------------
We support two ingestion modes:
1) **Preferred**: Signed upload flow (S3 presigned PUT)
   - Client requests an upload URL, then uploads raw bytes directly to storage.
   - Analyze/grade requests reference the stored object (upload_id / object_url).
2) **Fallback**: Base64 inline images in request bodies
   - Supported for quickstart/testing.
   - Not recommended for production mobile at scale.

Non-goals:
- No mandatory mobile SDK requirement for v1.

------------------------------------
DEVELOPER DOCS + EXAMPLES
------------------------------------
Docs must include:
- OpenAPI (authoritative contract)
- Copy/paste examples: curl, Node, Python
- Mobile examples: Swift/Kotlin/React Native snippets (minimal, no SDK requirement)
- Gatekeeper guide: how to handle accepted vs rejected outcomes
- Rate limiting and retry guidance

------------------------------------
PARTNER PORTAL + MULTI-TENANT SAAS
------------------------------------
We are building a **multi-tenant SaaS** (not D2C). Requirements:
- Partner web portal:
  - create org/workspace
  - create/rotate/revoke API keys
  - view usage (requests, accepts/rejects, error rates)
  - billing (at minimum invoices/plan; later metered billing)
- Multi-tenant architecture:
  - tenant isolation on data + billing + rate limits
  - per-tenant API keys and quotas
  - request logging and audit trail

------------------------------------
RATE LIMITING
------------------------------------
- Rate limiting must be tenant-aware.
- Return standard 429 responses with retry guidance.

