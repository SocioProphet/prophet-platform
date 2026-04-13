# Integration map

## Runtime home

`prophet-platform` is the runtime and deployment home for platform services.

## Upstream standards and references

Pinned upstream inputs include:
- `TriTRPC`
- `ontogenesis`
- `semantic-serdes`
- `socioprophet-standards-storage`
- `identity-is-prime-reference`
- `human-digital-twin`

## Current runtime layers

- `apps/api` -> internal TriTRPC bootstrap service
- `apps/gateway` -> browser-facing ingress relay and thin platform proxy surface
- `apps/socioprophet-web` -> portal shell
- `apps/eval-fabric-api` -> evaluation, observability, and intelligence lane backed by Postgres + ClickHouse
- `apps/knowledge-reason` -> governed claim-evaluation ingress scaffold
- `apps/lampstand` -> local-daemon integration target and receipt catalog emitter
- `apps/evidence-receipts` -> thin platform reader for emitted artifact bundles across current producer layouts, with gateway-read proxy support

## Data and schema anchors

- `contracts/` -> platform event, evidence, membrane, export, and receipt contracts
- `schemas/eval/` -> eval-fabric metric, fact, context-slice, and judge schemas

## Contract spine

- `EventEnvelope`
- `EvidenceReceipt`
- `MembraneDecision`
- `CarrierIngested`
- `ReceiptCatalogEntry`
