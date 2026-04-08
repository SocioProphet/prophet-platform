# Lampstand vertical slice

This platform slice proves that a local-daemon service can participate in the platform contract model without being forced into the cluster service shape.

## Flow

1. a file path is selected locally
2. the platform wrapper computes stable file metadata and content hash
3. it writes a `CarrierIngested` payload
4. it writes an `EventEnvelope`
5. it writes an `EvidenceReceipt`
6. it appends a `ReceiptCatalogEntry` to the local discovery catalog

## Why this matters

- the platform gains a real artifact/evidence path
- Lampstand remains a local service
- later services can consume the same receipt catalog model instead of inventing their own

## Current limits

- the discovery surface is local file-based, not yet a network API
- upstream Lampstand indexing can be layered in later once the upstream import is pinned
