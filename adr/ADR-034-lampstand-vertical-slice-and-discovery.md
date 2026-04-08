# ADR-034: Lampstand vertical slice and file-based discovery

## Status
Proposed

## Context

Lampstand is a local daemon, not a cluster-first microservice.
The platform needs one real end-to-end slice that proves contracts, receipts, and local-service
integration without distorting that service class.

Phase 3 established:
- canonical event / receipt contracts
- Lampstand as a local-daemon integration target

The missing piece is a real data path that the rest of the platform can discover.

## Decision

We will implement a local vertical slice for Lampstand using file-based discoverability:

- ingest a local file and emit `CarrierIngested`
- emit canonical `EventEnvelope` and `EvidenceReceipt`
- append a `ReceiptCatalogEntry` to a local JSONL catalog
- maintain `latest.json` as a convenience pointer for operator and platform tooling

The file-based catalog lives under the platform state root and is the first discovery surface.
We explicitly do **not** require Kubernetes wiring for this service class.

## Consequences

Positive:
- proves the contract family against a real artifact
- preserves the correct service boundary for Lampstand
- gives API/gateway and future services a stable discovery seam

Negative:
- discovery is local-first, not yet cluster-wide
- later phases must decide how and when to surface catalog data through platform services

## Follow-ons

- expose catalog reads through platform API/gateway if needed
- bring Agentplane outputs onto the same envelope/receipt/catalog model
- add membrane decisions and export approvals once identity services land
