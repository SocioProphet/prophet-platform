# cloudshell-fog Migration to Runtime v2

This document defines the migration path from the earlier runtime scaffolding to the preferred v2 deployment lanes.

## Why this migration exists

The initial runtime scaffolding established the basic platform footprint for `cloudshell-fog`, but the repaired v2 overlays are now the canonical runtime path.

Reasons:

- the v2 overlays patch the known runtime wiring defects
- the v2 lanes align with the policy lane and the deployment inventory model
- the standard and federal lanes are separated cleanly
- the go-live gate and production decision records are built around the v2 path

## Source and target

### Transitional source paths

- `infra/k8s/cloudshell-fog/overlays/runtime-default`
- `infra/k8s/cloudshell-fog/overlays/runtime-federal`
- older Argo runtime applications that point at those overlays

### Canonical target paths

- `infra/k8s/cloudshell-fog/overlays/runtime-v2-standard`
- `infra/k8s/cloudshell-fog/overlays/runtime-v2-federal`
- `infra/argocd/cloudshell-fog-runtime-v2-standard-application.yaml`
- `infra/argocd/cloudshell-fog-runtime-v2-federal-application.yaml`
- `infra/argocd/cloudshell-fog-stack-standard-application.yaml`
- `infra/argocd/cloudshell-fog-stack-federal-application.yaml`

## Migration steps

1. reconcile the policy lane first
2. complete the deployment inventory and production decision record for the chosen profile
3. deploy the matching v2 runtime application or stack application
4. stop promoting the old runtime overlays
5. once the environment is stable, retire the old runtime application references from operator practice

## Rule

No new environment should be promoted using the older runtime overlays.

They are retained only for continuity and repo history.

## What remains before full retirement

- real production values must replace the current placeholders
- the go-live validator must pass for the selected profile
- operators should stop using the old Argo application paths in runbooks and deployment habits
