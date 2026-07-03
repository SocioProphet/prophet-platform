# Branch Consolidation Plan — 2026-04-12

## Objective
Return `SocioProphet/prophet-platform` to a single surviving long-lived branch (`main`) while preserving all substantive branch-only work and explicitly discarding only known-noise or already-landed branches.

Temporary execution branch:
- `integration/land-all-20260412`

This branch is cut from current `main` and is the sole staging lane for reconciliation before merge-back.

## Current branch inventory

### Already absorbed by `main` (safe delete after verification)
- `feat/registri-knowledge-import-plan-v0`
- `ghost-v3-runtime-combined-pack-v1`
- `mdheller/market-data-profile-20260411`

These branches are behind `main` with `ahead_by = 0`.

### Explicit noise / likely discard
- `mdheller/tree-test`

This branch carries only `TREE_TEST.txt` and should not be landed unless explicitly retained for a reason.

### Unique branch work to preserve
- `arch/wordops-reference-architecture-v0-2`
- `arch/wordops-reference-architecture-v0-2-clean`
- `docs/next-gen-tom-spec-bundle`
- `eval-fabric-followup`
- `eval-fabric-runtime-followup`
- `evidence-native-assessment-v0b-2`
- `ghost-v3-runtime-combined-pack-v2`
- `mdheller/eval-fabric-evidence-pins-v1`
- `storage-convergence-slice-receipts`

## Key findings

### 1. Direct merge of old topic branches into current `main` is not the right move
Most remaining unique branches diverge from an older base and are between ~52 and ~81 commits behind current `main`.

Therefore:
- do **not** merge these heads directly into `main`
- instead transplant or cherry-pick their unique work onto the fresh integration branch

### 2. Some branch pairs are not simple supersets
#### WordOps pair
- `arch/wordops-reference-architecture-v0-2`
- `arch/wordops-reference-architecture-v0-2-clean`

These diverged from the same historical base and both modify overlapping WordOps docs. Treat `...-clean` as the likely canonical starting point, but manually reconcile content from the older branch before landing a single normalized commit.

#### Eval-fabric pair plus evidence-pins branch
- `eval-fabric-followup`
- `eval-fabric-runtime-followup`
- `mdheller/eval-fabric-evidence-pins-v1`

These branches share a historical base but are not strict supersets of one another. They require one deliberate eval-fabric reconciliation pass on top of current `main`.

### 3. Ghost V3 combined pack v2 is a true continuation of v1
- `ghost-v3-runtime-combined-pack-v2` is ahead of `...v1`
- `...v1` itself is already absorbed by `main`

Therefore only `...v2` needs to be landed.

## Recommended landing order

### Tranche A — low-risk additive landings
1. `storage-convergence-slice-receipts`
2. `evidence-native-assessment-v0b-2`
3. `docs/next-gen-tom-spec-bundle`
4. `ghost-v3-runtime-combined-pack-v2`

Rationale:
- mostly additive files
- low overlap with current `main`
- establishes visible progress before higher-conflict reconciliations

### Tranche B — WordOps reconciliation
Create one normalized commit from:
- `arch/wordops-reference-architecture-v0-2-clean`
- reconciled with any still-useful deltas from `arch/wordops-reference-architecture-v0-2`

Target outcome:
- one coherent WordOps documentation landing
- no surviving duplicate WordOps branch heads after merge

### Tranche C — Eval-fabric reconciliation
Create one integrated eval-fabric landing from:
- `eval-fabric-followup`
- `eval-fabric-runtime-followup`
- `mdheller/eval-fabric-evidence-pins-v1`

Target outcome:
- governance/provenance schemas
- updated eval-fabric docs
- test coverage and smoke path
- runtime/doc changes reconciled against current `main`

This tranche should be validated more aggressively than the others because it touches:
- `Makefile`
- runtime Python files
- tests
- infra manifests

## Execution method

For each tranche on `integration/land-all-20260412`:
1. transplant branch-only content onto the fresh branch rather than merging old heads directly
2. keep commits topic-scoped and readable
3. validate after each tranche
4. only after the full integration branch is coherent, merge once into `main`

## Validation expectations

Minimum:
- repo validation (`make validate`)
- service/runtime tests for eval-fabric if present
- storage validators for storage tranche
- inspect docs index / discoverability for newly landed docs

## Final cleanup after merge to `main`
Delete:
- `integration/land-all-20260412`
- `feat/registri-knowledge-import-plan-v0`
- `ghost-v3-runtime-combined-pack-v1`
- `mdheller/market-data-profile-20260411`
- `mdheller/tree-test`
- all topic branches that are fully represented in the merged integration result

## Desired end state
- one surviving long-lived branch: `main`
- all substantive branch-only work either merged or explicitly discarded with reason
- no stale historical branches left carrying unique but unlanded work
