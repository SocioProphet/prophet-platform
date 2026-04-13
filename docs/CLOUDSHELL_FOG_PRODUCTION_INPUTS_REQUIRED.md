# cloudshell-fog Production Inputs Required

This document enumerates the inputs that **must** be replaced or supplied before a `cloudshell-fog` deployment should be considered production-ready.

## 0. Why this exists

The repository now contains a coherent standard/federal deployment model, but several values remain intentionally unresolved because they are environment-specific and should not be guessed.

## 1. Required image inputs

The following must be replaced with real values:

- `ghcr.io/socioprophet/cloudshell-fog@sha256:REPLACE_WITH_PINNED_DIGEST`
- any example deployment inventory value using `sha256:REPLACE_WITH_REAL_DIGEST`

Rules:

- production must use pinned digests only
- the selected digest should match the intended standard or federal lane
- the selected digest should have the expected SBOM, signature, and provenance evidence

## 2. Required signature trust inputs

The vendored policy bundle currently includes a placeholder cosign public key block.

Before production:

- replace `REPLACE_WITH_REAL_COSIGN_PUBLIC_KEY`
- or adapt the policy to the selected keyless verification model

## 3. Required secret inputs

The runtime lane expects a Kubernetes secret named:

- `cloudshell-fog-secrets`

Required key:

- `session-token-signing-key`

This should be sourced by one of:

- secret manager + ExternalSecret-style sync
- sealed/encrypted secret workflow
- controlled bootstrap process documented for the environment

## 4. Required federal inputs

The federal lane currently carries a placeholder for the cloud fallback region in the repaired v2 overlay.

Before production federal deployment:

- replace `REPLACE_WITH_FEDERAL_FALLBACK_REGION`
- confirm that the selected region and trust posture are acceptable for the federal tenant/profile
- ensure the selected image line matches the documented FIPS/CMVP posture

## 5. Transitional assets not to use as canonical

Do not treat the older non-v2 runtime overlays as the preferred deployment path.

Preferred path:

- `infra/k8s/cloudshell-fog/overlays/runtime-v2-standard`
- `infra/k8s/cloudshell-fog/overlays/runtime-v2-federal`

## 6. Recommended operator sequence

1. resolve image digest(s)
2. resolve secret source and secret values
3. resolve signature trust material
4. resolve federal fallback region where applicable
5. run validators
6. reconcile policy lane
7. reconcile runtime v2 lane
