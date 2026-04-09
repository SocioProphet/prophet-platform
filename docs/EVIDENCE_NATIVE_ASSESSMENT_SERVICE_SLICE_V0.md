# Evidence-Native Assessment Service Slice v0

## Status

Plan document.

This document defines the thinnest acceptable service slice for evidence-native assessment in `prophet-platform`.

`prophet-platform` is the runtime and deployment hub. It should turn the canonical contracts and runtime bindings into running services without becoming the source of truth for the ontology itself.

## Upstream ownership

- contract canon: `SocioProphet/socioprophet-standards-storage`
- semantic context: `SocioProphet/socioprophet-standards-knowledge`
- policy source and compilation: `SocioProphet/policy-fabric`
- execution and receipt ownership: `SocioProphet/agentplane`

## Service goal

The first service slice must support one complete governed assessment run:
- accept evidence input references
- invoke claim extraction
- invoke control evaluation against a pinned policy bundle
- emit at least one finding
- persist receipt-bound output references
- expose a report-ready API surface without making the report the source of truth

## Minimal service set

### 1. Evidence intake service

Responsibilities:
- accept evidence references or uploaded evidence handles
- normalize source metadata
- calculate or verify digests
- emit references suitable for downstream extraction

Outputs:
- `EvidenceRef` set or an equivalent deterministic envelope

### 2. Claim extraction service

Responsibilities:
- consume evidence references
- invoke extractor(s)
- normalize extracted assertions
- preserve extractor identity and version

Outputs:
- `Claim` set
- optional `ClaimConflict` candidates discovered during extraction

### 3. Control evaluation service

Responsibilities:
- consume claims and pinned `ControlRequirement` material
- emit row-level `ControlCellEvaluation` objects
- preserve trace identity and policy bundle version

Outputs:
- `ControlCellEvaluation` set

### 4. Finding generation service

Responsibilities:
- convert non-pass or non-complete evaluations into reviewable findings
- preserve evidence refs and evaluation lineage
- attach remediation summary and closure criteria

Outputs:
- `Finding` set

### 5. Report/query service

Responsibilities:
- expose receipt-derived views for operators and downstream UI
- preserve drill-down to receipt, evaluations, and evidence refs

Outputs:
- `AssessmentReport` views

## Storage and transport posture

- internal service transport should use the platform TriTRPC binding
- receipt and evaluation references should remain typed and traceable
- evidence and report views should be derived from canonical receipt-bound objects rather than hand-maintained summaries

## Required invariants

1. Platform services must preserve trace id continuity.
2. Report responses must always link back to a receipt reference.
3. Coverage or score-like summaries must be derivable from underlying evaluation objects.
4. Services must not silently drop evidence classification or retention metadata.
5. A receipt without replay linkage is incomplete.

## Deployment posture

The v0 slice may run as a small number of services, but the logical boundaries above should remain explicit so that later scaling and isolation choices do not require contract redesign.

## Acceptance gate

The service slice is acceptable when the platform can demonstrate:
- one evidence intake path
- one claim extraction path
- one control evaluation path
- one finding-generation path
- one report/query path
- all outputs bound to one sealed assessment receipt
