# Integration map (phase 4 additions)

- `apps/lampstand/`
  - local-daemon integration target
  - emits `CarrierIngested`, `EventEnvelope`, `EvidenceReceipt`
  - appends `ReceiptCatalogEntry`
- `contracts/ReceiptCatalogEntry.v0.1.json`
  - platform-local discoverability record for receipts and payloads
- `tools/validate_phase4_vertical_slice.py`
  - proves the Lampstand vertical slice end to end
