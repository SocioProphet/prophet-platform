# Wave 0 — supply chain + promotion hardening

The first, no-cluster-risk wave of the E2E deployment plan: make deploys
**signed, ordered, and gated** without touching running workloads. Three
self-contained changes.

## 1. Keyless image verification (Kyverno)

`infra/policy/cloudshell-fog/kyverno/verify-signed-images.yaml` no longer carries
a placeholder public key. It now verifies **keyless** (Sigstore/Fulcio)
signatures against the estate's GitHub Actions OIDC identity
(`issuer: https://token.actions.githubusercontent.com`,
`subject: https://github.com/SocioProphet/*`, Rekor transparency log). Nothing to
rotate or leak. This enforces the `require_signature_state` promotion requirement
at admission.

## 2. Argo sync-waves

`infra/k8s/argo-cd/appsets/socioprophet-appset.yaml` now assigns each Application a
`argocd.argoproj.io/sync-wave` from the dependency tiers already documented in the
file: storage/vector-store (wave 0) → mesh core → graph kernel (wave 8) → product
front-ends (waves 11–13). Argo waits for each wave to be Healthy before the next,
so consumers never start ahead of what they depend on.

## 3. Promotion enforcer

`tools/gitops_promote_image.py` gates channel promotion (dev→stage→prod) against
the `promotion_requirements` in `contracts/platform/deployment-profiles.yaml`
(`require_digest` / `require_signature_state` / `require_sbom` /
`require_provenance`). It refuses to pin a digest into a channel's values unless
the CI-supplied verification summary satisfies every declared requirement; on pass
it writes the pinned digest. 6 unit tests in `tools/tests`.

```
tools/gitops_promote_image.py --service hellgraph-service --channel prod \
  --digest sha256:<64hex> --values-file deploy/values/hellgraph-service.yaml \
  --profiles contracts/platform/deployment-profiles.yaml --signed --sbom --provenance
```

## Depends on (separate repo)

Producing the signatures + SBOM + SLSA provenance is the reusable
`SocioProphet/.github` `build-image.yml` workflow's job (cosign keyless sign +
syft SBOM attestation + provenance). This wave makes the platform **require and
verify** them; wiring the producer side is the paired change there.

## Not in this wave

Observability backend (the keystone), Cilium mesh, Argo Rollouts (A-B/canary),
Chaos Mesh, HPA/KEDA — see the E2E readiness plan.
