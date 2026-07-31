# WordOps / Sherlock Matrix substrate — Layer 1 (homeservers)

Production kustomize deployment for the two Synapse estates described in
`docs/WORDOPS_MATRIX_HOMESERVER_DEPLOYMENT_PROFILE.md`. Ported from the local
profile in `infra/wordops/matrix/`.

This is **Layer 1** of the substrate program (homeservers). Layers 2–4
(room-factory/governance-as-code, Sherlock bot, admin runbooks) build on top.

## What this deploys

| Estate | Server name | Exposure | Posture |
|---|---|---|---|
| **public edge** | `matrix.socioprophet.ai` | public Ingress (GCE + ManagedCert), federation over 443 | intake/self-service; no public room directory; no regulated content |
| **private core** | `matrix-core.socioprophet.internal` | cluster-internal only (no Ingress) | case/incident/agent rooms; federation disabled (empty whitelist); E2EE posture enforced in Layer 2 |

Each estate = `Synapse v1.131.0` (pinned) + `Postgres 16` (StatefulSet, 10Gi PVC)
+ a media PVC (20Gi) + a persisted signing key. An `nginx` edge fronts the
public estate and serves `.well-known/matrix/{client,server,support}`.

```
base/
  synapse-public.yaml    # ConfigMap + ExternalSecret + Postgres STS/Svc + Synapse Deploy/Svc/PVC + NetworkPolicy
  synapse-private.yaml   # symmetric, locked down
  matrix-edge.yaml       # nginx edge + Service + BackendConfig + ManagedCertificate + Ingress
  kustomization.yaml
overlays/p0-lab/         # namespace: socioprophet
```

## Secrets — never in the repo

All secrets are pulled at runtime via **ExternalSecret** (external-secrets.io),
matching `infra/k8s/sovereign-broker`. Before deploy, fill in and seed:

- `REPLACE_WITH_ESTATE_SECRETSTORE` → the estate's `SecretStore` name
- `REPLACE_WITH_REMOTE_KEY_PATH/...` → Secret Manager paths for, per estate:
  `db-password`, `registration-shared-secret`, `macaroon-secret`, `form-secret`,
  `signing-key` (generate the signing key **once** and persist it — losing it
  breaks federation identity).

## Security gates (from the deployment profile)

| Gate | Status |
|---|---|
| TLS configured | ✅ GKE ManagedCertificate on the public edge |
| Registration policy explicit | ✅ `enable_registration: false` both estates |
| Public room directory blocked | ✅ `allow_public_rooms_*: false` |
| Federation posture | ✅ public: 443; private: disabled (empty whitelist) |
| Signing key persisted | ✅ from Secret Manager via ExternalSecret |
| Secrets out of config/repo | ✅ ExternalSecret + secret-fragment merge |
| Presence off | ✅ both estates |
| Admin account provisioning | ⏳ deferred (documented runbook — Layer 4) |
| Moderation bot | ⏳ deferred (Layer 3 Sherlock bot / Mjolnir) |
| Backup/restore tested | ⏳ deferred (Postgres + media backup runbook) |
| Media retention policy | ⚠️ partial (`max_upload_size` set; full policy TBD) |
| E2EE posture check (private) | ⏳ enforced in Layer 2 governance |

## Decisions made (confirm in review)

1. **In-cluster Postgres** (StatefulSet + PVC), not CloudSQL — matches the
   profile's "named Postgres volume + backup" and keeps the estate self-contained.
   Swap to CloudSQL later by pointing `database.args.host` at the instance.
2. **Server names**: `matrix.socioprophet.ai` (public) / `matrix-core.socioprophet.internal`
   (private). Change here + in the ConfigMaps/Ingress/ManagedCert if you prefer others.
3. **Federation over 443** via `.well-known/matrix/server` — avoids a separate
   `:8448` LoadBalancer.

## Smoke checks (post-deploy)

- `curl https://matrix.socioprophet.ai/_matrix/client/versions` → 200
- `curl https://matrix.socioprophet.ai/.well-known/matrix/client` → homeserver JSON
- private: `kubectl -n socioprophet exec deploy/synapse-private -- curl -s localhost:8008/_matrix/client/versions`
- registration disabled: `POST /_matrix/client/v3/register` → `M_FORBIDDEN`
- public room publication blocked until moderation baseline is enabled

**Not deployed by this PR** — applying to the cluster is a gated action.
