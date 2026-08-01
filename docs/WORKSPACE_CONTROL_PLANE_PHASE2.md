# Workspace Control Plane — Phase 2 (capability broker)

Implements **Phase 2** of the control spec: local capability manifests + MCP
discovery + a **deterministic capability broker** (spec D7). Gets a controlled
"go fish" working safely, on top of the Phase-1 frozen schemas, before remote
overlays exist.

## What it does

`tools/capability_broker.py` resolves a requested capability across sources in a
**fixed order** — `local_manifest -> local_affordance -> mcp_server ->
trusted_catalog -> remote_join` — as sequenced by a `discovery-policy.v0`. The
planner never crawls arbitrarily.

Every candidate passes a **trust gate** derived from the policy's
`trust_requirements`:

- `require_signed` -> manifest must carry a signature.
- expiry -> manifest must be unexpired at `now`.
- `require_revocation_check` -> a revocation field must be present and not revoked.
- `trusted_catalog` lane -> the manifest id must be listed in a **valid**
  `catalog-entry.v0` (unexpired, signed, delegation threshold met).

The first trusted match wins, and the broker emits a provenance **`event.v0`**
(`CapabilityResolved` / `CapabilityUnresolved`) — append-only and object-centric.

## Conformance

Sources are `capability-manifest.v0`, policy is `discovery-policy.v0`, catalogs
are `catalog-entry.v0`, and emitted events validate against `event.v0` — all
Phase-1 frozen schemas. Tests: deterministic order, trust rejections
(unsigned/expired/revoked/missing-revocation), catalog gating, and event
conformance. Path-filtered CI: `.github/workflows/control-plane-broker.yml`.

## Next (Phase 3)

Connector roots (local files, Google Drive, OneDrive, Box, Apple/iCloud) with
delta + watch and scoped mounts — producing assets/events against the Phase-1
object model.
