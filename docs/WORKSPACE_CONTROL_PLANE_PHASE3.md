# Workspace Control Plane — Phase 3 (connector roots)

Implements **Phase 3** of the control spec: connector roots with per-root policy,
delta/incremental sync, scoped mounts, and the mirror/live/action rails (D3/D4),
on the Phase-1 object model. The local-files connector is fully working and
credential-free; cloud connectors declare their delta+watch mechanism and are
gated behind credentials.

## Contracts (frozen, `contracts/workspace-control-plane/schemas`)

- `account.v0` (D3) — external account; holds a credential **reference**, never the secret.
- `capability-grant.v0` (D3) — per-account scopes with expiry + revocation.
- `root.v0` (D3/D4) — per-root `sync_mode` (mirror | live | action), `cache_policy`,
  `allowed_actions`, `delta_cursor`, `watch`.
- `mount.v0` (D3) — least-privilege, user-selected scope over a root.

## Rails (D4)

| Rail | Behavior |
|---|---|
| **mirror** | Produce indexed asset copies (`asset.v0`) + events. |
| **live** | Just-in-time: emit events only, no cached asset. |
| **action** | Side effects only — handled by `workflow-run`, not ingestion. |

## Connectors (`tools/connector_roots.py`)

- **LocalFilesConnector** — fully implemented: walks a local dir, emits governed
  `asset.v0` + `event.v0`, content-addressed (sha256), incremental via an mtime
  delta cursor. Honors the rail.
- **Cloud connectors** (credential-gated; `sync`/`watch` raise until wired, naming
  the mechanism):
  - Google Drive — `changes.getStartPageToken + changes.list`; `changes.watch` push.
  - OneDrive/SharePoint — Graph `delta`/`deltaLink` (deleted facet); Graph subscriptions.
  - Box — events/`stream_position`; Box webhooks.
  - Apple iCloud — `NSMetadataQuery` over the ubiquitous-documents scope;
    security-scoped bookmarks for restart-safe access.

## Validation

New schemas + examples are validated by the existing control-plane contract
validator; `tools/tests/test_connector_roots.py` proves the local connector emits
schema-valid assets/events, the delta cursor is incremental, each rail behaves,
and cloud connectors are credential-gated. Path-filtered CI:
`.github/workflows/control-plane-connectors.yml`.

## Next (Phase 4)

Mirror/live/action rail orchestration + the attention registry (`attention-mark.v0`).
