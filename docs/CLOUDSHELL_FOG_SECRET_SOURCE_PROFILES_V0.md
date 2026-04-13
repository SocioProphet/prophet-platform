# cloudshell-fog Secret Source Profiles v0

This document defines the supported secret-source patterns for `cloudshell-fog` in `prophet-platform`.

## 0. Why this exists

The runtime lane requires a Kubernetes secret named `cloudshell-fog-secrets`, but the platform repo should not silently assume one provider or bootstrap mechanism.

This document makes the supported patterns explicit.

## 1. Recommended profile: ExternalSecret / secret manager sync

Recommended for production:

- source secret material from a managed secret system
- sync into Kubernetes through an ExternalSecret-style controller
- keep the generated Secret name stable as `cloudshell-fog-secrets`

Why this is preferred:

- rotation can be centralized
- bootstrap remains cleaner than hand-managed static secrets
- the deployment repo does not need to carry raw secret values

## 2. Acceptable fallback: controlled manual bootstrap

Acceptable for early environments and break-glass situations:

- create `cloudshell-fog-secrets` manually or via a controlled bootstrap step
- ensure the source and rotation procedure are documented outside the manifest itself

This is not the preferred long-term production pattern.

## 3. Deferred patterns

Possible later patterns:

- sealed/encrypted secret workflow
- environment-specific secret operators or managed integrations

These are intentionally not hard-coded here because the current platform repo does not yet carry an existing organisation-wide secret-source convention.

## 4. Minimum required key

The runtime lane currently requires:

- secret name: `cloudshell-fog-secrets`
- required key: `session-token-signing-key`

## 5. Operator rule

An environment is not ready until:

- the secret-source pattern is chosen
- the resulting Kubernetes Secret exists or is guaranteed to be reconciled
- the readiness validator passes without unresolved placeholder tokens
