# agents.md — PreGrade / PreGrade Intelligence

This file defines **non-negotiable rules** for all automated agents (AI or otherwise) contributing to this repository.

Failure to follow these rules invalidates the work.

---

## 1. AUTHORITATIVE PRODUCT DEFINITION

This repository implements **decision intelligence**, NOT grading.

PreGrade exists to answer:
> “Is this card worth grading?”

It does **not**:
- Assign PSA, BGS, TAG, or any other grades
- Predict prices with certainty
- Replace professional grading companies
- Act as an authority

All outputs are **advisory, probabilistic, and explainable**.

---

## 2. STRICT NON-GOALS (DO NOT VIOLATE)

Agents MUST NOT:

- Implement grading logic (e.g. “PSA 9”, “BGS 10”, etc.)
- Use grading authority language
- Add population reports or census data
- Introduce subjective or “magic” scores
- Add consumer UI, dashboards, or frontend code
- Add features not explicitly requested
- Refactor unrelated code
- Optimise prematurely
- Add TODOs or placeholders in production code

If unsure whether something violates scope → **do not implement it**.

---

## 3. SCOPE ISOLATION RULE

Each task will define an explicit scope.

Agents MUST:
- Implement **only** what is requested
- Touch **only** files required for that task
- Avoid architectural changes unless explicitly instructed

Agents MUST NOT:
- “Improve” surrounding code
- Anticipate future features
- Combine multiple responsibilities in one change

One task = one responsibility.

---

## 4. DETERMINISM REQUIREMENT

Given the same inputs, the system MUST produce the same outputs.

Agents MUST:
- Avoid hidden randomness
- Avoid non-deterministic ordering
- Avoid time-dependent logic unless explicitly required

If probabilistic reasoning is used:
- The probability model must be explicit
- The reasoning must be explainable

---

## 5. EXPLAINABILITY IS MANDATORY

Every decision MUST include:

- Clear reason codes
- Human-readable explanations
- Traceable inputs → outputs

Agents MUST NOT:
- Produce scores without explanation
- Collapse multiple reasons into vague summaries
- Use unexplained weights or thresholds

If a decision cannot be explained, it should not exist.

---

## 6. GATEKEEPER RULES (CRITICAL)

Gatekeeper rejections are:
- Valid outcomes
- Expected outcomes
- Billable outcomes

Agents MUST:
- Treat rejection paths as first-class logic
- Return structured rejection reasons
- Never “force” a positive outcome

A rejection is not a failure.

---

## 7. LANGUAGE AND POSITIONING RULES

Agents MUST use language that is:

- Neutral
- Advisory
- Non-authoritative

Agents MUST NOT use language implying:
- Certainty
- Final judgement
- Official grading status

Preferred phrasing:
- “Recommendation”
- “Likelihood”
- “Risk band”
- “Confidence”

Forbidden phrasing:
- “Grade”
- “Guaranteed”
- “Official”
- “Certified”

---

## 8. FILE OWNERSHIP & STRUCTURE

Agents MUST respect the repository structure.

- `/domain` → pure domain models
- `/services` → business logic
- `/api` → request/response handling
- `/infrastructure` → AWS, storage, integrations
- `/docs` → product documentation

Do not blur responsibilities across layers.

---

## 9. COST AWARENESS

Agents MUST assume:
- This system will run at scale
- Cost per request matters

Agents SHOULD:
- Prefer simple, cheap solutions first
- Avoid heavy dependencies unless justified
- Avoid excessive logging unless required

---

## 10. WHEN IN DOUBT

If an agent is unsure about:
- Product intent
- Business rules
- Scope boundaries

The correct action is to:
> **Stop and request clarification**

Not to guess.

---

## 11. FINAL RULE (MOST IMPORTANT)

PreGrade wins or loses on **trust in rejection**.

Any change that reduces:
- Explainability
- Determinism
- Rejection confidence

Is a regression.

Protect the gatekeeper.
