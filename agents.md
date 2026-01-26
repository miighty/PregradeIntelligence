# Agent Operating Rules (STRICT)

This repository is for **PreGrade – Grading Intelligence API**, a backend decision-intelligence service. These rules are **non-negotiable** and apply to all future changes.

## 1) Scope isolation (task discipline)
- Only do what the current task explicitly asks for.
- Do not “helpfully” add features, endpoints, databases, workers, queues, SDKs, CLIs, IaC stacks, billing, or ML pipelines unless explicitly requested.
- Do not refactor, rename, reorganize, or reformat unrelated code. Keep diffs minimal and relevant.

## 2) Non-goals are hard constraints
- Do not implement **PSA/BGS/CGC grade assignment** or any grader-emulation logic.
- Do not add population reports, price prediction claims, or “investment advice” language.
- Do not add a consumer UI or any user-facing frontend in this repo.

## 3) Language and tone constraints (no authority language)
- Never claim authority over grading (e.g., “This card is a PSA 10”, “Guaranteed gem mint”, “Certified grade”).
- Use ROI framing and decision-support language only (e.g., “recommended to grade given inputs and assumptions”).
- Any recommendation must be framed as **decision intelligence** with stated assumptions and traceable reasons.

## 4) Determinism is required
- The same input must produce the same output.
- Do not introduce nondeterminism (randomness, unstable ordering, time-dependent outputs, environment-dependent behavior).
- If randomness is ever required by an explicit future requirement, it must be controlled via deterministic seeding and documented—otherwise prohibited.

## 5) Explainability is first-class
- Every decision must include **structured reason codes** and human-readable explanations.
- Do not introduce black-box decisions without traceable reasoning.
- Rejections are valid outcomes and must be expressed as structured gatekeeper results with reason codes.

## 6) No business logic implementation unless explicitly requested
- Do not implement the grading recommendation engine, ROI logic, gatekeeper rules, identity resolution logic, or any production decision flow unless the task explicitly asks for it.
- Scaffolding, docs, typing, and structural setup are allowed only when requested.

## 7) Data and privacy hygiene (baseline)
- Do not log raw images or sensitive customer identifiers by default.
- Prefer structured logs and redact secrets (API keys, tokens). Never print secrets to console.
- Do not hardcode credentials, API keys, or private URLs.

## 8) Changes must be production-quality
- Keep documentation explicit and accurate.
- Do not add TODOs, placeholders, pseudocode, or speculative roadmaps unless explicitly requested.
- If you add configuration or tooling, keep it minimal and directly justified by the task.

