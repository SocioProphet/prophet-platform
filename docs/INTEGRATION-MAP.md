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

- `apps/api` -> internal bootstrap service
- `apps/gateway` -> browser-facing ingress relay
- `apps/socioprophet-web` -> portal shell
- `apps/lampstand` -> local daemon integration target

## Contract spine

- `EventEnvelope`
- `EvidenceReceipt`
- `MembraneDecision`
- `CarrierIngested`
- `ReceiptCatalogEntry`
