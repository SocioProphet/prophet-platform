# hellgraph-superpeer — the cloud-twin graph replica

Runs in the **cloud-twin cluster**. **STATUS: staged, NOT yet active.** The manifests + super-peer
image exist and the federation is proven in hellgraph tests, but the live path is not wired: the
edge StatefulSet does not run in federation mode (publishes no base key) and the
`hellgraph-federation` ConfigMap holds a placeholder. Until the edge is a federation participant
AND the twin is verified replicating, `edge-twin-sync` stays the PRIMARY sync (every 30m) — do
not demote it before then.

Intended end state — the twin's graph view comes from the hellgraph **federation** (a live,
causally-merged replica of the edge's sovereign log) instead of a periodic RocksDB blob, unifying
the two edge↔cloud-twin sync stacks:

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

1. **Image mode** — the `ghcr.io/socioprophet/hellgraph` image is the mode-aware
   `apps/hellgraph-service` (now vendoring **@socioprophet/hellgraph 0.4.4** — the hardened engine).
   `HELLGRAPH_MODE=superpeer` selects the federation-replica role over the default local service —
   one image, two roles, no `command` override. The edge must also run in federation mode (be the
   federation creator) so it has a base key to publish.
2. **Base key** — the edge is the federation creator; publish its `baseKey()` once into the
   `hellgraph-federation` ConfigMap (`data.base-key`):
   `kubectl -n socioprophet get --raw /api/v1/.../hellgraph:8850/health` → `.baseKey`, or have the
   edge write it on startup. It is a **public join identity**, not a secret.
3. **Auth secret (required to start)** — provision the `hellgraph-superpeer-auth` Secret (key
   `auth-secret`) via ExternalSecret (see `hellgraph-superpeer-auth.externalsecret.example.yaml`).
   `HELLGRAPH_AUTH_SECRET` arms bearer auth on `/health /cut /query /admit`; without it the engine
   runs OPEN, so the Deployment requires the Secret and will not start until it exists (fail-closed
   by design — the ExternalSecret is intentionally not in `kustomization.yaml`). Generate a token
   with `openssl rand -hex 32`. Consumers must then send `Authorization: Bearer <token>`.
4. **Probes & metrics** — liveness/readiness hit the PUBLIC `/livez` (unauthenticated by design);
   `/health` is behind auth and would 401 the kubelet. Prometheus scrapes the PUBLIC `/metrics`
   (pod annotations), network-restricted to this namespace by the baseline NetworkPolicy.
5. Consumers query the twin at `hellgraph-superpeer:8850/query` (SPARQL/Gremlin/MeTTa/Cypher) — the
   same read surface as the edge, but served from the replicated view, with a bearer token.

## Relationship to edge-twin-sync

`infra/k8s/edge-twin-sync` is demoted to **daily cold DR** (was every 30m). It remains as a blob
backup for catastrophic recovery; day-to-day convergence is this federation replica.
