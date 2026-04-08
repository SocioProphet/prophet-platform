# ADR-033: Canonical receipts and event envelopes

## Status
Proposed

## Context
The platform already has seed event contracts (`TopicAssigned`, `EmbeddingComputed`, `LensOutput`)
that embed lightweight receipts. As more services arrive, especially local daemons, the platform
needs a canonical event/evidence shape so receipts can be replayed, audited, correlated, and
indexed consistently.

## Decision
Introduce the following platform-wide schemas:

- `contracts/EventEnvelope.v0.1.json`
- `contracts/EvidenceReceipt.v0.1.json`
- `contracts/MembraneDecision.v0.1.json`
- `contracts/CarrierIngested.v0.1.json`
- `contracts/ScopeRef.v0.1.json`
- `contracts/ExportApproved.v0.1.json`
- `contracts/ExportDenied.v0.1.json`

Rules:
1. Every runtime service emits an `EventEnvelope`.
2. Every materially completed action emits an `EvidenceReceipt`.
3. Policy/membrane services emit `MembraneDecision`.
4. Service-specific domain events reference the canonical receipt.

## Consequences
- Existing contracts remain valid but should gradually add `evidence_receipt_ref`.
- Receipts become first-class platform artifacts.
- Local daemon services can participate in governance and replay without pretending to be cluster
  microservices.
