# evidence-receipts

Minimal platform reader service for emitted payload / `EventEnvelope` / `EvidenceReceipt` artifacts.

## Why it exists

`eval-fabric-api` and `lampstand` now emit local platform artifacts, but the platform also needs a reader surface so those artifacts become consumable platform state rather than dead files.

## Current scope

- read recent receipt bundles for a service
- fetch a specific bundle by correlation/stem
- read recent catalog entries when the producer maintains a catalog (currently Lampstand)
- support the current canonical platform artifact layout:
  - `prophet-platform/{payloads,events,receipts}/<service>`
- retain legacy compatibility for historical service-first layouts:
  - `prophet-platform/<service>/{payloads,events,receipts}`

## Endpoints

Direct service endpoints:
- `/healthz`
- `/v1/services`
- `/v1/receipts/recent?service=<name>&limit=<n>`
- `/v1/receipts/{service}/{correlation_id}`
- `/v1/catalog/recent?service=<name>&limit=<n>`

Gateway-proxied endpoints:
- `/v1/evidence/services`
- `/v1/evidence/receipts/recent?service=<name>&limit=<n>`
- `/v1/evidence/receipts/{service}/{correlation_id}`
- `/v1/evidence/catalog/recent?service=<name>&limit=<n>`

## Limits

This is intentionally a reader, not yet a long-running indexer or dashboard cache. It should stay thin until the producers and contract model stabilize further.
