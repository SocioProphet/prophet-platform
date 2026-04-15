# cloudshell-fog Upstream Validation Matrix v0

This document records how the `cloudshell-fog` lane in `prophet-platform` aligns to upstream organisational standards, protocols, and adjacent repos.

## Purpose

The goal is to make `cloudshell-fog` convergence against the rest of the SocioProphet estate explicit and reviewable.

## Validation matrix

| Area | Upstream reference | Current local binding | Status |
|---|---|---|---|
| GitOps / CI-CD | `SocioProphet/prophet-platform-standards/adr/ADR-040-tekton-argocd-gitops.md` | `contracts/cloudshell-fog/runtime-governance-binding-v0.json` | Bound |
| Signed manifests | `SocioProphet/prophet-platform/docs/FOGSTACK_SIGNED_MANIFESTS.md` and `tools/attach_fogstack_manifest_signature.py` | `docs/CLOUDSHELL_FOG_RELEASE_EVIDENCE_V0.md` and release-evidence validator | Bound |
| Trust profile | `SocioProphet/sociosphere/protocol/agentic-workbench/v1/trust_profiles/control-plane.v0.1.json` | runtime governance binding + access profile | Bound |
| Fog Stack Access offering | connected Fog Stack Access docs / bundle docs | `docs/CLOUDSHELL_FOG_FOGSTACK_ACCESS_BINDING_V0.md` and `contracts/cloudshell-fog/fogstack-access-profile-v0.json` | Bound |
| Compatibility / release evidence | local contracts + manifests | compatibility statement + component-version manifest + release-evidence validator | Bound |
| Runtime deployment lane | repaired local v2 overlays | runtime-v2 guide + v2 path validator | Bound |
| Legacy runtime lane retirement | transitional markers only | `TRANSITIONAL.md` markers and migration guide | Partial |
| Production truth | real digest / secret source / trust material / federal fallback region | production decision records and go-live gate exist, but real values not committed | Open |

## Interpretation

### Bound
The upstream reference is identified and a local platform artifact exists that clearly ties `cloudshell-fog` to it.

### Partial
A migration or deprecation path exists, but the old path still remains operationally visible.

### Open
The required operator or environment truth has not yet been committed.

## Rule

A production promotion should not be treated as fully upstream-aligned until the `Open` row above is closed and the `Partial` row for legacy runtime retirement is resolved.
