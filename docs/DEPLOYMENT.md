# Deployment — Prophet Platform

## Overview

Prophet Platform uses **GitOps** with Argo CD and Kustomize for all environment deployments.

---

## Environments

| Environment | Overlay path | Notes |
|-------------|--------------|-------|
| `dev`       | `infra/k8s/overlays/dev/` | Fast iteration; no TLS enforcement |
| `prod`      | `infra/k8s/overlays/prod/` | Full mTLS + sealed secrets |

---

## How deployments work

1. Changes merged to `main` automatically trigger CI (`.github/workflows/ci.yml`).
2. CI builds and pushes container images.
3. Argo CD detects the manifest change in `infra/k8s/` and syncs the target cluster.

---

## Manual sync (emergency / first-time setup)

```bash
# Preview changes
kubectl apply --dry-run=client -k infra/k8s/overlays/<env>

# Apply
kubectl apply -k infra/k8s/overlays/<env>

# Or via Argo CD
argocd app sync prophet-platform
```

---

## Secrets management

All secrets are stored as Kubernetes Secrets and referenced from workload manifests.
For production, use [sealed-secrets](https://github.com/bitnami-labs/sealed-secrets) or equivalent.

Key secret: `TRITRPC_AEAD_KEY` (32-byte hex) — see [RUNBOOK.md](RUNBOOK.md#rotating-secrets).

---

## Rollback

See [RUNBOOK.md](RUNBOOK.md#rolling-back-a-deployment).

---

## Container image policy

- Images are pinned by digest in production overlays.
- Signature verification via Cosign/Sigstore is planned (see [ROADMAP.md](ROADMAP.md)).
