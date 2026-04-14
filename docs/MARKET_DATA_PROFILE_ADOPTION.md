# Market Data Runtime Profile Adoption

| Field | Value |
| --- | --- |
| Status | Draft integration note |
| Runtime repo | `SocioProphet/prophet-platform` |
| Runtime profile authority | `SocioProphet/prophet-platform-standards` |
| Upstream storage authority | `SocioProphet/socioprophet-standards-storage` |
| Profile commit | `a99a71c22dfbb3a3d8beac6f0369f7f83cd3bb73` |
| Profile path | `docs/profiles/market-data-runtime-profile-v0.md` |

## Purpose

This file records the runtime-side adoption point for the market-data runtime profile.
It exists so the platform repo is explicitly aware of the profile and its upstream
storage authority split.

## Authority split

- Storage contexts, canonical data formats, and benchmark methodology remain governed by
  `SocioProphet/socioprophet-standards-storage`.
- Runtime conformance rules for market-data ingest, normalization, replay, receipts,
  and operator controls are defined in
  `SocioProphet/prophet-platform-standards/docs/profiles/market-data-runtime-profile-v0.md`.
- Workspace namespace ownership and cross-repo registry visibility are maintained in
  `SocioProphet/sociosphere`.

`prophet-platform` MUST NOT redefine storage contexts locally.

## Immediate implementation targets

The following `prophet-platform` surfaces SHOULD conform as market-data work lands:
- `contracts/` for normalized market-data event contracts and receipts
- `schemas/` for runtime-facing schema references
- `docs/STORAGE_INTEGRATION_BLUEPRINT.md` for runtime/storage mapping notes
- smoke helpers and replay workers for staleness, gap detection, and deterministic replay

## Next integration steps

1. Pin the profile in `standards.lock.yaml` once the initial profile branch merges.
2. Add concrete market-data contracts for quotes, trades, bars, and replay receipts.
3. Extend smoke helpers to validate staleness, late/out-of-order handling, and replay determinism.
4. Keep any storage-semantic change proposals upstream in `socioprophet-standards-storage`.
