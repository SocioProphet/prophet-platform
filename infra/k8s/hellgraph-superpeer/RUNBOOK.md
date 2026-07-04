# hellgraph-superpeer — go-live runbook

How to bring the cloud-twin super-peer from **staged** to **serving**. The manifests + hardened
engine (0.4.4) are merged; this is the operator sequence to provision secrets, join the edge
federation, deploy, and verify. Everything here targets the `socioprophet` namespace in the
cloud-twin cluster.

> The twin is a **disposable read-replica** (Deployment + emptyDir, never a writer). Rolling it
> back or losing it is safe — it re-derives from the edge's log; the edge stays sole authority and
> `infra/k8s/edge-twin-sync` remains the cold-DR path.

## 0. Preconditions

```sh
# gcloud + cluster creds (the currently-blocking step — needs interactive re-auth)
gcloud auth login
gcloud container clusters get-credentials <cluster> --region <region> --project <project>

kubectl get ns socioprophet                                 # namespace exists
kubectl get crd externalsecrets.external-secrets.io          # External Secrets Operator installed
kubectl -n socioprophet get svc hellgraph                    # the EDGE service (federation creator)
```

The edge must be running **in federation mode** (it's the federation creator, so it has a base key
to publish). If it isn't, the twin has nothing to join.

## 1. Provision the auth secret — REQUIRED (the pod will not start without it)

`HELLGRAPH_AUTH_SECRET` arms bearer auth on the sensitive routes (`/health` `/cut` `/query`
`/admit`). The Deployment consumes it from the `hellgraph-superpeer-auth` Secret (key
`auth-secret`), which is deliberately **not** in `kustomization.yaml` — so the twin fails closed
(won't start) rather than run OPEN.

```sh
TOKEN=$(openssl rand -hex 32)
```

**Option A — ESO (production).** Store `$TOKEN` in the cluster's secret backend under property
`hellgraph_superpeer_auth_secret`, then copy `base/hellgraph-superpeer-auth.externalsecret.example.yaml`
to a real (non-`.example`) file, fill in `secretStoreRef.name` + `remoteRef.key`, and apply it. ESO
materializes the `hellgraph-superpeer-auth` Secret.

**Option B — direct (bootstrap / non-prod).**
```sh
kubectl -n socioprophet create secret generic hellgraph-superpeer-auth \
  --from-literal=auth-secret="$TOKEN"
```

Keep `$TOKEN` — same-namespace consumers need it (step 5).

## 2. Publish the edge federation base-key

The twin joins the edge's federation by its **base key** (a 64-hex *public join identity*, not a
secret). Read it from the edge's health and write it into the `hellgraph-federation` ConfigMap
(key `base-key`, which currently holds the `REPLACE_WITH_EDGE_BASE_KEY_64_HEX` placeholder):

```sh
BASEKEY=$(kubectl -n socioprophet exec deploy/hellgraph -- \
  curl -s localhost:8850/health | jq -r .baseKey)

kubectl -n socioprophet create configmap hellgraph-federation \
  --from-literal=base-key="$BASEKEY" \
  --dry-run=client -o yaml | kubectl apply -f -
```

## 3. Deploy

The super-peer is **not yet wired into an ArgoCD Application**. Two paths:

- **Manual bring-up:** `kubectl apply -k infra/k8s/hellgraph-superpeer/base -n socioprophet`
- **GitOps (preferred once unblocked):** add an ArgoCD `Application` pointing at
  `infra/k8s/hellgraph-superpeer/base` and sync it. This is where the **ArgoCD sync blocker
  (#700)** must be cleared first.

## 4. Verify

```sh
kubectl -n socioprophet rollout status deploy/hellgraph-superpeer

# public liveness (unauthenticated by design — this is what the kubelet probes hit)
kubectl -n socioprophet exec deploy/hellgraph-superpeer -- curl -sf localhost:8850/livez
#   → {"ok":true}

# auth is ENFORCED on sensitive routes
kubectl -n socioprophet exec deploy/hellgraph-superpeer -- curl -s -o /dev/null -w '%{http_code}\n' localhost:8850/health
#   → 401   (no token)
kubectl -n socioprophet exec deploy/hellgraph-superpeer -- \
  curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $TOKEN" localhost:8850/health
#   → 200

# metrics (public route; namespace-restricted by the baseline NetworkPolicy)
kubectl -n socioprophet exec deploy/hellgraph-superpeer -- curl -s localhost:8850/metrics | head

# replication smoke: write a node at the EDGE, then confirm it materializes in the twin's view
kubectl -n socioprophet exec deploy/hellgraph-superpeer -- \
  curl -s -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"lang":"gremlin","query":"g.V().count()"}' localhost:8850/query
```

## 5. Consumers

In-cluster consumers query `hellgraph-superpeer:8850/query` (SPARQL / Gremlin / MeTTa / Cypher) and
**must send `Authorization: Bearer $TOKEN`**. The baseline NetworkPolicy already restricts ingress
to the same namespace.

## Rollback

```sh
kubectl -n socioprophet delete -k infra/k8s/hellgraph-superpeer/base
```

Safe: the twin is a rebuildable derived index. The edge remains sole authority and `edge-twin-sync`
(cold DR) is untouched.

## Open gates (as of 2026-07-04)

- [ ] gcloud interactive re-auth (step 0)
- [ ] ArgoCD sync blocker #700 (step 3, GitOps path)
- [ ] Provision `hellgraph-superpeer-auth` secret (step 1) + publish edge base-key (step 2)
