# Evidence Receipt Spine Consumption Mapping

## Status

Generated/platform-facing consumption note.

## Purpose

`prophet-platform` already has legacy platform receipt contracts such as `contracts/EvidenceReceipt.v0.1.json`.

The SocioProphet standards layer now also defines a cross-repo evidence receipt spine in `SocioProphet/socioprophet-standards-storage`:

- `ObservationReceipt`
- `ValidationReceipt`
- `PromotionReceipt`
- `PublicationReceipt`
- `ExecutionReceipt`
- `ReplayReceipt`

This note defines how platform runtime evidence should consume that spine without replacing existing platform-local receipts in one disruptive step.

## Current platform receipt shape

The existing platform `EvidenceReceipt` uses these core fields:

- `receipt_id`
- `created_at`
- `service_ref`
- `action`
- `status`
- `subject_ref`
- `evidence_refs`
- `output_refs`
- `hash`
- `hash_algo`

## Canonical receipt-spine shape

The standards receipt spine uses these core fields:

- `id`
- `kind`
- `specVersion`
- `subjectRef`
- `issuedTimeUtc`
- `scopeRef`
- `policyWitnessThreshold`
- `witnesses`
- `contentSpaceRef`
- `provenanceRootRef`
- `evidenceRefs`
- `upstreamReceiptIds`

## Field bridge

| Platform receipt field | Receipt spine field |
|---|---|
| `receipt_id` | `id` |
| `created_at` | `issuedTimeUtc` |
| `subject_ref` | `subjectRef` |
| `evidence_refs` | `evidenceRefs` |
| `policy_refs` | `policyRefs` / policy-derived evidence refs |
| `correlation_id` | `provenanceRootRef` or upstream receipt correlation |

## FogStack runtime evidence mapping

The first platform consumer is FogStack runtime/deployment evidence.

| Platform/FogStack artifact class | Receipt spine kind |
|---|---|
| release validation records | `ValidationReceipt` |
| promotion policy / approval / publication gate records | `PromotionReceipt` / `PublicationReceipt` |
| runtime dry-run records | `ExecutionReceipt` |
| AgentPlane run linkage records | `ExecutionReceipt` |
| parity readiness records | `ReplayReceipt` when used as replay/proof boundary, otherwise `ValidationReceipt` |
| local demo artifact index / digest proof | `ValidationReceipt` or upstream `evidenceRefs` |

## Non-goals

This consumption mapping does not:

- delete or replace `contracts/EvidenceReceipt.v0.1.json`;
- claim runtime emission of canonical receipt-spine objects yet;
- mutate FogStack runtime behavior;
- alter the local demo parity command;
- redefine `socioprophet-standards-storage` schemas.

## Implementation path

1. Pin `socioprophet-standards-storage` at a commit containing the receipt spine.
2. Add a platform-local mapping contract under `contracts/evidence/`.
3. Add a generated mapping fixture under `docs/generated/evidence/examples/`.
4. Add a validator proving the mapping bridge remains coherent.
5. Later emit canonical receipt-spine records from FogStack runtime evidence paths.
