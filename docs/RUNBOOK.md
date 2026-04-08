# Operations Runbook — Prophet Platform

## Overview

This runbook covers day-to-day operations for the Prophet Platform.
See [LOCAL-DEV.md](LOCAL-DEV.md) for local development setup and
[DEPLOYMENT.md](DEPLOYMENT.md) for deployment details.

---

## Prerequisites

- Docker / Podman
- Go 1.22+
- Node 20+ with corepack enabled (`corepack enable`)
- `kubectl` + access to target cluster (for k8s operations)
- `argocd` CLI (optional, for GitOps inspection)

---

## Health check

```bash
# Validate repo structure and doc sanity
make validate

# Check API service health (when running locally)
curl http://localhost:8080/health
```

---

## Starting services locally

See [LOCAL-DEV.md](LOCAL-DEV.md) for the full local dev workflow.

---

## Applying infrastructure changes

Infrastructure is managed with **Kustomize + Argo CD**.

```bash
# Preview what would change (dry-run)
kubectl apply --dry-run=client -k infra/k8s/overlays/<env>

# Argo CD sync (preferred path in CI/CD)
argocd app sync prophet-platform
```

---

## Rolling back a deployment

```bash
# Via Argo CD (preferred)
argocd app rollback prophet-platform

# Manual (last resort)
kubectl rollout undo deployment/<name> -n prophet-platform
```

---

## Rotating secrets

1. Generate a new 32-byte AEAD key: `openssl rand -hex 32`
2. Update the Kubernetes Secret (or sealed secret) in `infra/k8s/`.
3. Restart affected workloads: `kubectl rollout restart deployment -n prophet-platform`

---

## CI pipeline reference

CI runs on every push/PR via `.github/workflows/`:

| Workflow       | Trigger          | What it does                        |
|----------------|------------------|-------------------------------------|
| `ci.yml`       | push/PR → main   | Build Go apps + build web app       |
| `validate.yml` | push/PR          | `make validate` (doc + dir sanity)  |

---

## Escalation path

If something is broken and you're not sure where to look:

1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
2. Review recent Argo CD sync history.
3. Check pod logs: `kubectl logs -n prophet-platform -l app=<name> --tail=100`.
4. Review [OBSERVABILITY.md](OBSERVABILITY.md) for metrics/tracing guidance.
