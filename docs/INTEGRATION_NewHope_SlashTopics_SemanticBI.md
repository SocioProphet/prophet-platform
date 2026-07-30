# New Hope + Slash Topics + Semantic BI — Platform Integration v0.1

## Scope
This document defines how **New Hope** (semantic runtime) and **Slash Topics** (governed, signed scopes) integrate to support **semantic BI** as a *platform capability*.

We treat this as a platform concern (SocioSphere domain), not an OS concern (SourceOS domain).

## Core idea
- **New Hope Carriers** are the event envelope: signed, content-addressed, policy-contextualized.
- **Slash Topic Packs** are the governed scope objects: signed artifacts that define what `/topic` means and which policies attach.
- **Semantic BI** consumes the resulting event stream + indexes and produces audited, replayable “lens outputs.”

## Canonicality (single source of truth)
- Canonical **Carrier / Membrane input semantics**: New Hope spec
- Canonical **Topic Pack schema + MembraneDecision schema**: Slash Topics specs
- Canonical **semantic-search-bi** capability contract: SocioSphere (platform)
- SourceOS may *mirror* platform contracts for packaging/ops, but is not canonical for platform meaning.

## Mapping: Slash Topics → New Hope policy_context
We map a slash scope into New Hope’s policy context:
- `policy_context.tenant`: `commons | org:<id> | team:<id>`
- `policy_context.community`: `topic:/<slash>` (example: `topic:/science`)
- `policy_context.ruleset_ref`: content hash of the policy bundle attached to the topic pack
- `policy_context.labels`: safety + routing labels (e.g., `contains_pii:false`, `source:social:x`, `egress:blocked`)

## Event flow (minimum viable vertical slice)
1) **Social ingest** → `MessagePosted` carrier
2) **Membrane** evaluates carrier → emits `MembraneDecision` (ALLOW / DENY / QUARANTINE / REDACT / REQUIRE_SIGNATURE)
3) **Topic projection** assigns one or more slash topics → emits `TopicAssigned` carrier(s)
4) **Vectorization** computes topic-aligned vectors (default deterministic classical methods) → emits `EmbeddingComputed` carrier + receipt
5) **Semantic BI** runs lens pipelines over scoped data → emits `LensOutput` carriers + receipts

## Safety posture
- Default to deterministic representations (LSA/LSI) unless governance explicitly enables encoder models.
- Prefer “downgrade fidelity” flows: keep embeddings/receipts when raw text is not allowed.
- Enforce explicit egress: no silent third-party calls.

## Canonicalization
- For TritRPC-transported carriers: hash/sign **canonical TritRPC frame bytes**.
- For JSON topic packs/manifests/policies: hash/sign **canonical JSON bytes** (RFC 8785/JCS recommended) + BLAKE3 naming.

