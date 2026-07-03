# Spine Rollout Plan (v0.1)

## Purpose
This document stages the rollout of the AgentOS / SourceOS spine so we can integrate tools without breaking canonical standards, violating trust boundaries, or baking replaceable providers into the substrate.

## Canonical authority map
- **SourceOS / SourceOS-adjacent bootstrap**: OS substrate rules, capability packaging pattern, opt-in runtime posture.
- **sociosphere**: workspace composition, materialization, lockfile authority, cross-repo validation.
- **TriTRPC**: deterministic wire protocol and fixture truth.
- **socioprophet-standards-storage** and **socioprophet-standards-knowledge**: normative standards and bindings.
- **socioprophet-agent-standards**: cross-repo guardrails, compatibility profile, and canonical-source mapping.
- **agentplane**: execution evidence lifecycle.
- **tritfabric**: opt-in runtime lane only.

## Non-negotiable rules
1. **Git + AIWG artifacts are authoritative** for work products.
2. **One canonical source** per capability contract package.
3. Risky/non-permissive providers run **behind adapters** and **outside the core lane**.
4. No service that touches user data or opens listeners ships enabled-by-default.
5. Standards repos define meaning and constraints; workspace/runtime repos validate and implement them.

## Drift risks to control early
### semantic-search-bi duplication
If multiple repos carry different definitions of the same capability package, validation becomes theater. Pick one canonical source and mirror the other.

### TriTRPC pin divergence
The standards binding and the materialized workspace must agree on the same TriTRPC revision. If they do not, fail the workspace validator.

### License ambiguity
Any repo missing a clear permissive license, or carrying contradictory license texts, stays out of the distributable core lane until resolved.

## Rollout phases
### Phase 0 — Hygiene and legal clarity
- Ensure each spine repo exposes `make validate` or `make verify`.
- Add/normalize licenses where missing or ambiguous.
- Remove `.DS_Store`, `.venv`, `.pyc`, and similar noise from canonical repos.
- Add CI gates for hygiene and license posture.

### Phase 1 — Spine validation
- Materialize the spine repos in `sociosphere`.
- Run a single workspace validator that checks:
  - standards validate
  - TriTRPC verify
  - SourceOS spec/cap validation
  - agentplane schema validation
  - TriTRPC pin consistency
  - capability-package drift

### Phase 2 — Base Linux substrate
- Keep SourceOS/host behavior minimal and local-first.
- Default to rootless/user-space tooling.
- Ship optional services disabled.
- Prefer UDS over TCP for local runtimes.

### Phase 3 — Adapter integration
Integrate third-party tools **only through adapters**:
- Executor → OpenCode, Goose, Aider, Continue
- BrowserOps → Stagehand, browser-use
- MemoryAPI → Mem0
- MeaningGraphAPI → AD4M (boxed)
- KnowledgeBaseAPI → Fortemi (boxed)

### Phase 4 — Opt-in runtimes
- Bring up tritfabric local-only first.
- Bring up agentplane evidence flows next.
- Keep experimental/non-permissive providers isolated behind service boundaries.

## First vertical slice
Prove the architecture on one narrow slice before broad rollout:
1. Materialize workspace with sociosphere.
2. Validate the spine.
3. Intake a task with AIWG.
4. Orchestrate with Gastown.
5. Execute with OpenCode (second-pass with Goose/Aider as needed).
6. Emit evidence through agentplane.
7. Index summaries into Mem0.
8. Use Stagehand only if the slice needs a browser step.

## Promotion rules
A component may enter the core lane only when:
- its license posture is acceptable,
- it is behind an adapter boundary,
- it has a task contract,
- it has an opt-in story if it is sensitive,
- and it does not become a competing standards authority.
