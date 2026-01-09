# infra/

This directory contains deployment wiring for Prophet Platform.

Principles:
- GitOps-friendly layout (Argo CD appsets, Kustomize base/overlays)
- Environment separation lives under `infra/k8s/.../overlays/*`
- No secrets committed; use SOPS/age or equivalent

Entry points:
- `infra/k8s/` (seeded from the legacy scaffold)
