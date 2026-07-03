# PKG step 5 — edge ↔ cloud-twin sync

Finishes the Personal Knowledge Graph stack (diagram-4). The per-person graph is
**edge-resident** (HellGraph on TopoLVM flash, PR #675); a **cloud twin** holds
canonical. This wires the sync between them.

## Mechanism

- **Profile** — `p-edge` added to `deployment-profiles.yaml` with an
  `edge_twin_sync` block (direction `edge_to_twin`, 30m cadence, `reference_only`
  privacy).
- **`sync-cronjob.yaml`** — every 30m an rclone Job co-locates on the HellGraph
  node (TopoLVM volumes are node-local), mounts its RocksDB store **read-only**,
  and pushes a timestamped copy to the S3-compatible twin. The twin keeps
  point-in-time copies; the edge stays authoritative for the live graph.
- **`volumesnapshotclass.yaml`** — `topolvm-snapshots` for **crash-consistent**
  point-in-time snapshots (the consistency-upgrade path: snapshot → restore to a
  temp PVC → rclone that, instead of copying an open RocksDB store).
- **`serviceaccount.yaml`** + **`*.externalsecret.example.yaml`** — the sync
  identity + the twin rclone creds (via external-secrets; example only).

## Privacy

Only **non-private projections** are meant to cross the link — the
`ProviderProjection` membrane (prophet-workspace `PersonalContextGraph`) governs
what may ever be exported. Private nodes stay on-device.

## Needs a live cluster / follow-ups

- Depends on the durable HellGraph StatefulSet ([#675](https://github.com/SocioProphet/prophet-platform/pull/675)) — the CronJob mounts its PVC `hellgraph-store-hellgraph-0`.
- Copying an open RocksDB store is best-effort consistent; use the VolumeSnapshot
  path for strict PITR (a snapshot-rotation companion is the next refinement).
- Reverse path (twin → new edge bootstrap/restore) is the paired follow-up.
- rclone image + chart-free; the twin bucket/creds come from the ExternalSecret.
