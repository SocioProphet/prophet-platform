# Reproducibility — Prophet Platform

## Overview

Reproducibility means that given the same inputs (code, config, secrets), any operator
can produce an identical running system. This document records how Prophet Platform
achieves (and where it falls short of) that goal today.

---

## What is reproducible today

| Area | How |
|------|-----|
| Go builds | `go.mod` + `go.sum` pin all dependencies |
| Web builds | `pnpm-lock.yaml` pins all npm dependencies |
| Infrastructure | Kustomize manifests in `infra/k8s/` are declarative and version-controlled |
| Validation | `make validate` is deterministic and dependency-free (stdlib Python only) |

---

## What is not yet reproducible

| Area | Gap | Roadmap item |
|------|-----|--------------|
| Container images | No pinned-digest builds yet | ROADMAP step 7 / image policy |
| AEAD key provisioning | Manual secret creation step required | ROADMAP step 2 |
| Argo CD bootstrap | First-time cluster setup is undocumented | To be added |

---

## Reproducing a local build from scratch

```bash
git clone https://github.com/SocioProphet/prophet-platform.git
cd prophet-platform

# Go services
cd apps/api/cmd/socioprophet-api && go build -v . && cd -
cd apps/gateway/cmd/tritrpc-gateway && go build -v . && cd -

# Web app
corepack enable
cd apps/socioprophet-web && pnpm install --frozen-lockfile && pnpm build && cd -

# Validation
make validate
```

All four steps should succeed with no external network access beyond module downloads.

---

## Dependency pinning policy

- Go: use `go mod tidy` + commit `go.sum`.
- Web: use `pnpm install --frozen-lockfile` in CI; never `--no-lockfile`.
- Infrastructure images: pin to digest in production overlays (enforced when image policy lands).
