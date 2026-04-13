# banking-twin-ingest

Twin ingest and normalization entrypoint for GAIA banking state payloads.

## Status

Staging scaffold only. This directory exists to freeze slice identity, purpose,
and upstream contract expectations before real pipeline code lands.

## Expected upstream refs

- GAIA banking semantic refs
- Ontogenesis banking ontology refs
- standards-storage banking contract refs
- TriTRPC banking transport/service refs
- agentplane banking execution bundle refs (where applicable)

## Expected runtime contract bindings

- `contracts/EventEnvelope.v0.1.json`
- `contracts/EvidenceReceipt.v0.1.json`

## Planned local files (future tranche)

- `pipeline_platform.py`
- `receipts.py` (or shared import)
- `runtime.py`
- adapter stubs / projection helpers
- fixture payloads
