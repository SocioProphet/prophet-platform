# Banking Runtime Slice Preparation (Staging Tranche)

This tranche prepares four banking runtime slices inside `prophet-platform`:

- `apps/banking-twin-ingest/`
- `apps/banking-scenario-run/`
- `apps/banking-capital-rollforward/`
- `apps/banking-filing-assembler/`

## Purpose

The goal is to establish the runtime lane boundaries and contract expectations
before implementation details sprawl across the repo.

This staging tranche mirrors the existing receipt-emitting vertical-slice pattern
used by `apps/storage-promotion/`, but does **not** yet implement the full banking logic.

## Upstream semantic inputs

These runtime slices assume:
- GAIA banking-firm profile and first banking domain manifests exist
- Ontogenesis banking ontology tranche exists
- standards-storage banking contracts and benchmark tranche exists
- TriTRPC banking service catalog and transport binding exist
- agentplane banking execution bundles exist

## Shared contract posture

All banking slices are expected to bind to:
- `contracts/EventEnvelope.v0.1.json`
- `contracts/EvidenceReceipt.v0.1.json`

Each slice SHOULD eventually emit:
- an event envelope
- an evidence receipt
- one or more output refs
- correlation identity tied to the semantic subject of the run

## Slice boundaries

### banking-twin-ingest
Input:
- banking twin state payload
- profile/domain refs
- tenant scope

Output:
- normalized state artifact
- event envelope
- evidence receipt

### banking-scenario-run
Input:
- twin snapshot ref
- scenario ref
- model pack refs

Output:
- projected state artifact
- event envelope
- evidence receipt

### banking-capital-rollforward
Input:
- projected state ref
- policy/model refs

Output:
- capital state snapshot
- ratio package
- event envelope
- evidence receipt

### banking-filing-assembler
Input:
- ratio package ref
- lineage/evidence refs
- correction policy refs

Output:
- filing pack
- event envelope
- evidence receipt

## Acceptance for this tranche

This preparation tranche is acceptable when:
1. each banking slice has a stable path and purpose,
2. each slice documents required upstream refs and outputs,
3. the repo contains a validator that checks the staging layout,
4. no banking runtime code lands that outruns the semantic and standards tranches.
