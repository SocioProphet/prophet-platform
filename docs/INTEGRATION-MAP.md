# Integration map

## Runtime home

`prophet-platform` is the runtime and deployment home for platform services.

## Upstream standards and references

Pinned upstream inputs include:
- `TriTRPC`
- `ontogenesis`
- `semantic-serdes`
- `new-hope`
- `memory-mesh`
- `slash-topics`
- `socioprophet-standards-storage`
- `identity-is-prime-reference`
- `human-digital-twin`

## Current runtime layers

- `apps/api` -> internal TriTRPC bootstrap service
- `apps/gateway` -> browser-facing ingress relay and thin platform proxy surface
- `apps/socioprophet-web` -> portal shell
- `apps/eval-fabric-api` -> evaluation, observability, and intelligence lane backed by Postgres + ClickHouse; canonical runtime now lives in `app.main`
- `apps/knowledge-reason` -> governed claim-evaluation ingress scaffold
- `apps/lampstand` -> local-daemon integration target, receipt catalog emitter, and zone-aware carrier ingress seam
- `apps/semantic-bridge` -> imported contract validation lane for envelope and membrane shapes
- `apps/zone-router` -> zone-aware publication and topic-resolution lane
- `apps/evidence-receipts` -> thin platform reader for emitted artifact bundles across current producer layouts, with gateway-read proxy support
- `apps/openai-research-mcp` -> research MCP runtime starter

## Data and schema anchors

- `contracts/` -> platform event, evidence, membrane, export, and receipt contracts
- `contracts/imported/` -> pinned upstream contract mirrors needed for runtime validation
- `schemas/eval/` -> eval-fabric metric, fact, context-slice, and judge schemas

## Contract spine

- `EventEnvelope`
- `EvidenceReceipt`
- `MembraneDecision`
- `CarrierIngested`
- `ReceiptCatalogEntry`

## First zone-aware flow

1. `apps/lampstand` ingests a local file and emits payload, event envelope, evidence receipt, and receipt-catalog entry.
2. zone metadata (`zone_ref`, optional `topic_ref`) is preserved with the local artifacts.
3. `apps/semantic-bridge` validates the envelope or membrane shape before cross-zone publication.
4. `apps/zone-router` resolves the publish target for the next lane.
5. `apps/knowledge-reason` remains the governed claim-evaluation ingress scaffold for promoted receipts and carriers.
