# hellgraph-superpeer — the cloud-twin graph replica

Runs in the **cloud-twin cluster**. Makes the twin's graph view come from the hellgraph
**federation** — a live, causally-merged replica of the edge's sovereign log — instead of
restoring a periodic RocksDB blob. This unifies the two edge↔cloud-twin sync stacks:

```
            live convergence (this)                       cold DR (daily)
edge hellgraph  ──Hypercore log──▶  hellgraph-superpeer      edge rclone ──blob──▶ S3 twin
(sovereign      (Autobase causal      (read-replica, /query)  (belt-and-suspenders,
 authority)      merge, no central                             see infra/k8s/edge-twin-sync)
                 authority)
```

## Why a Deployment (not a StatefulSet) with emptyDir

The twin is a **disposable index**, not a source of truth. It re-derives from the edge's log via
the federation on restart, and it is **never admitted as a writer** — so it cannot forge or
rewrite, and there is **no split-brain**: the edge stays sole authority. The proof is in the
hellgraph repo (`superpeer-federation.test.ts`): a node written at the edge materializes in the
twin's `/query` with no blob sync, and the causal cut shows the edge as a writer while the twin is
absent from it. Storage intent is `derived_index` (rebuildable, never egressed).

## Wiring (prerequisites)

1. **Image mode** — the `ghcr.io/socioprophet/hellgraph` image must include the super-peer
   entrypoint (`bin/hellgraph-superpeer.mjs`, hellgraph PR #13) and be re-vendored/rebuilt. The
   Deployment runs it via `command: ["node", "bin/hellgraph-superpeer.mjs"]`. The edge must also
   run in federation mode (be the federation creator) so it has a base key to publish.
2. **Base key** — the edge is the federation creator; publish its `baseKey()` once into the
   `hellgraph-federation` ConfigMap (`data.base-key`):
   `kubectl -n socioprophet get --raw /api/v1/.../hellgraph:8850/health` → `.baseKey`, or have the
   edge write it on startup. It is a **public join identity**, not a secret.
3. Consumers query the twin at `hellgraph-superpeer:8850/query` (SPARQL/Gremlin) — the same
   read surface as the edge, but served from the replicated view.

## Relationship to edge-twin-sync

`infra/k8s/edge-twin-sync` is demoted to **daily cold DR** (was every 30m). It remains as a blob
backup for catastrophic recovery; day-to-day convergence is this federation replica.
