# Lampstand platform vertical slice

This wrapper adds a platform-native evidence path around Lampstand.

## Commands

- `pp-lampstand ingest --path <file>`
  - computes file metadata and content hash
  - writes `CarrierIngested`
  - writes `EventEnvelope`
  - writes `EvidenceReceipt`
  - appends a catalog record
- `pp-lampstand discover --limit N`
  - reads back the latest catalog entries

## Important boundary

The wrapper owns:
- contract emission
- local catalog append
- platform-specific path layout

Upstream Lampstand should continue to own:
- file indexing internals
- query behavior
- daemon lifecycle
