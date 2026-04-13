# cloudshell-fog Runtime v2 Guide

This guide defines the **preferred deployment path** for cloudshell-fog inside `prophet-platform`.

## 0. Why v2 exists

Earlier runtime scaffolding established the rough platform shape, but the v2 overlays are the first lane intended to be treated as canonical.

Reasons:

- profile and deployment patching are explicit
- standard and federal lanes are separated cleanly
- secret/image inventory expectations are now documented
- policy is deployable as a separate Argo application

## 1. Use these lanes

Preferred runtime overlays:

- `infra/k8s/cloudshell-fog/overlays/runtime-v2-standard`
- `infra/k8s/cloudshell-fog/overlays/runtime-v2-federal`

Preferred Argo applications:

- `infra/argocd/cloudshell-fog-policy-application.yaml`
- `infra/argocd/cloudshell-fog-runtime-v2-standard-application.yaml`
- `infra/argocd/cloudshell-fog-runtime-v2-federal-application.yaml`

## 2. Treat these older lanes as transitional

The earlier non-v2 runtime overlays should not be treated as the preferred deployment target.

They remain in-repo for continuity, but operators should converge on the v2 overlays and associated inventory/secret contracts.

## 3. Required operator inputs

Before deploying:

- choose `standard` or `federal` profile
- supply a real pinned digest for `ghcr.io/socioprophet/cloudshell-fog`
- supply `cloudshell-fog-secrets` with `session-token-signing-key`
- verify the selected policy lane is reconciled

## 4. Standard lane

Use when:

- managed cloud trust tier is acceptable
- strict federal posture is not required

Key characteristics:

- `minimum_trust_tier = managed_cloud`
- `strict_egress = false`
- `require_fips_validated_crypto = false`

## 5. Federal lane

Use when:

- stricter trust posture is required
- FIPS-oriented crypto posture is required
- egress controls must be tighter

Key characteristics:

- `minimum_trust_tier = attested_fog`
- `strict_egress = true`
- `require_fips_validated_crypto = true`

## 6. Recommended deployment order

1. reconcile policy lane
2. validate inventory and secrets
3. reconcile runtime v2 lane
4. run smoke checks
