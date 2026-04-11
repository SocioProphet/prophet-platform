# cloudshell-fog Integration v0

This document defines how `cloudshell-fog` should be integrated into `prophet-platform`.

## 0. Role split

- `SocioProphet/cloudshell-fog` remains the product/spec repository for the shell gateway, placement model, policy baseline, and deployment profile.
- `SocioProphet/prophet-platform` is the runtime and deployment hub where those upstream decisions become concrete platform assets.

This repository should therefore consume `cloudshell-fog`, not replace it.

## 1. Expected platform footprint

The natural footprint inside `prophet-platform` is:

### 1.1 `apps/`

Add an application package for `cloudshell-fog` containing:

- gateway deployment wiring
- runtime image references
- environment-specific configuration overlays
- optional future sidecar/mesh integration hooks

Suggested path:

- `apps/cloudshell-fog/`

### 1.2 `infra/`

Add deployment wiring for:

- namespace definitions
- ingress/gateway configuration
- network policy references
- policy application references
- Argo CD application / overlay bindings

Suggested paths:

- `infra/k8s/cloudshell-fog/`
- `infra/argocd/cloudshell-fog/`

### 1.3 `contracts/`

Add platform-facing contracts for:

- session lifecycle events
- placement decisions
- policy denials
- runtime allocation receipts

These contracts do not need to replace the browser-facing HTTP/WSS surface. They represent platform-side consumption and observability.

### 1.4 `tools/`

Add:

- smoke-health checks for the shell gateway
- drift checks for deployment references and policy bundles
- validation that required policy artifacts are present in platform overlays

## 2. Protocol boundary inside prophet-platform

`prophet-platform` is TriTRPC-centric for internal service runtime topology, but `cloudshell-fog` should retain its product boundary:

- browser/operator surface: OIDC + HTTPS/JSON + WSS
- platform/internal integration: may later gain TriTRPC or CloudEvents bindings where useful

Current rule:

- do not force the browser-facing shell API through TriTRPC
- keep TriTRPC for platform-internal service interactions where it materially helps

## 3. Mesh stance inside prophet-platform

The current recommended stance from `cloudshell-fog` is:

- optional Istio at the stable platform boundary
- no default mesh enrollment for per-session runtime pods
- Admiral deferred until there is a real multicluster Istio automation burden

The place to instantiate that choice is here in `prophet-platform`, not in the product repo.

## 4. FIPS / FedRAMP consequences for prophet-platform

`cloudshell-fog` now carries a compliance profile aimed at FIPS-aligned cryptographic posture and FedRAMP-compatible deployment.

For `prophet-platform`, that means:

- define a federal/fips deployment profile rather than assuming all environments are equal
- preserve evidence for image digests, signatures, provenance, SBOMs, and crypto-module selection
- ensure deployment overlays can distinguish stricter federal lanes from ordinary deployment lanes
- keep ingress, egress, audit, and runtime-policy configuration explicit and reviewable

This repository should not claim FedRAMP authorization by virtue of carrying the service. It should provide the deployment and evidence wiring that makes a federal-compatible environment achievable.

## 5. Immediate downstream backlog

1. add `apps/cloudshell-fog/`
2. add `infra/` overlays and Argo references for cloudshell-fog
3. add platform-facing contracts for session / placement / policy events
4. add smoke and validation hooks under `tools/`
5. define the federal/fips deployment lane for this service

## 6. Result

Within prophet-platform, `cloudshell-fog` should become:

- a deployable platform service
- a policy- and provenance-aware shell gateway
- a fog-aware runtime placement consumer
- a standards-native browser edge that coexists with the broader TriTRPC platform spine
