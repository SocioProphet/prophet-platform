# cloudshell-fog app scaffold

This directory represents the `cloudshell-fog` service as a platform-managed application inside `prophet-platform`.

## Upstream source of truth

Product and specification ownership remain upstream in:

- `SocioProphet/cloudshell-fog`

This platform repo owns only the runtime and deployment consequences:

- selected image digests
- environment overlays
- platform ingress/gateway wiring
- policy bundle references
- smoke and validation hooks

## Design stance

- Browser/operator surface remains OIDC + HTTPS/JSON + WSS.
- TriTRPC remains a platform-internal transport concern rather than the browser-facing shell API.
- Session runtimes stay out of the mesh by default.
- Optional Istio ingress/egress or stable control-plane mesh integration is a downstream platform decision.

## Federal / FIPS profile

Where a federal deployment profile is required:

- use the `infra/k8s/cloudshell-fog/overlays/federal/` overlay
- preserve digest/signature/SBOM/provenance evidence
- use a runtime/gateway image line with documented FIPS/CMVP posture
- enforce stricter trust-tier and egress assumptions

## Follow-on work

- replace placeholder image references with pinned digests from the production lane
- connect policy bundles from the upstream repo into platform overlays
- add platform-facing contracts for session and placement events
