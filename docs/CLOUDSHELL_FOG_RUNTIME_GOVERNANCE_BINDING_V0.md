# cloudshell-fog Runtime Governance Binding v0

This document binds the `cloudshell-fog` runtime/deployment lane in `prophet-platform` to existing organisation-level governance conventions rather than treating it as an isolated service.

## Purpose

The platform already has stronger conventions elsewhere for:

- Tekton + ArgoCD GitOps
- signed Fog Stack manifests
- trust-profile driven control-plane execution

This document states that `cloudshell-fog` is expected to align to those conventions.

## Bound references

### GitOps / CI-CD baseline

- `SocioProphet/prophet-platform-standards/adr/ADR-040-tekton-argocd-gitops.md`

This is the accepted platform strategy for:
- Tekton build/test/provenance/signing
- ArgoCD GitOps reconciliation
- immutable audit trail expectations

### Signed bundle-manifest baseline

- `SocioProphet/prophet-platform/docs/FOGSTACK_SIGNED_MANIFESTS.md`
- `SocioProphet/prophet-platform/tools/attach_fogstack_manifest_signature.py`

These define the current repo-native meaning of a signed Fog Stack bundle manifest.

### Trust-profile baseline

- `SocioProphet/sociosphere/protocol/agentic-workbench/v1/trust_profiles/control-plane.v0.1.json`

This provides a strong candidate upstream trust vocabulary for:
- attestation requirements
- approval quorum
- required ledger/audit semantics
- fail-closed posture
- egress grant requirements

## What this means for cloudshell-fog

The `cloudshell-fog` platform lane should be interpreted as requiring, over time:

- GitOps deployment through the accepted Tekton/Argo model
- signed Fog Stack manifest packaging for release candidates
- a trust-aware operational posture consistent with the control-plane trust profile where relevant
- explicit evidence references for promotion and higher-risk deployment decisions

## Non-goal

This document does not claim that all those conventions are already fully automated for `cloudshell-fog`.

It defines the governance alignment target so the current platform lane can converge on existing organisation-wide standards rather than inventing its own isolated rules.
