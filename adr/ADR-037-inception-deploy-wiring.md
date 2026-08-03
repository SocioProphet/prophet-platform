# ADR-037 — Inception service: steady-state GitOps deploy wiring

**Status:** Proposed (2026-08-03)
**Context decision:** "Wire the Cybernetic Genesis *Inception* runtime into the estate's ArgoCD
steady-state deploy, digest-pinned and held — reviewable, not live."

Companion to ADR-036 (Inception Framework invariants). ADR-036 is the *what runs*; this is the
*how it deploys*. The build+push half lives in `SocioProphet/cybernetic-genesis`
(`.github/workflows/image.yml`, `deploy/overlays/prod`, `deploy/DECISIONS.md`).

## Context

Inception's image was built, promoted to estate GAR
(`us-central1-docker.pkg.dev/socioprophet-platform/socioprophet/inception`, amd64 digest
`sha256:423b4ae6…`, tag `81fd3cc-amd64`), deployed to live GKE in an `inception-validation`
namespace, verified Ready + serving, then torn down. The GAR artifact and the self-contained kustomize
overlay remain. What was missing is the steady-state ArgoCD wiring.

The estate pattern (verified by reading `deploy/argocd/{alert-delivery,pvc-capacity-guard,
registry-services,socbase-services,runtime-services}.yaml`):

- Application/ApplicationSet manifests live under **`deploy/argocd/`** — the ONLY tree the
  tofu-created root app-of-apps (`infra/tofu/environments/gcp-gke/argocd.tf`) recurses. Anything under
  `infra/argocd/` is never reconciled.
- Every existing Application sets `source.repoURL = prophet-platform` and a kustomize/helm `path`
  **in this repo**.
- `project: default`, `destination.server: kubernetes.default.svc`.
- Each carries `socioprophet.io/tier: foundation|reference` (preflight_deploy_contract.py check 5).
- Steady-state norm is `syncPolicy.automated:{prune,selfHeal}` + `CreateNamespace=true`.
- Images are digest/sha-pinned; moving tags (`:latest`) are a hard preflight failure (checks 3/4).

## Decision

Add `deploy/argocd/inception-services.yaml`: a single `kind: Application` following that pattern, with
two deliberate deviations, each recorded below.

### D1 — External source repo (deviation from repoURL = self)

Inception's deploy manifests are owned by, and versioned in, the public MIT repo
`SocioProphet/cybernetic-genesis` (self-contained kustomize: `base` + `base-support` +
`overlays/prod`). So this Application sets `repoURL = cybernetic-genesis`, `path =
deploy/overlays/prod`. The **digest pin lives with the service that owns it** (that overlay's kustomize
`images:`), not in prophet-platform.

**Cost of the deviation:** `tools/preflight_deploy_contract.py` is static and walks only in-repo paths,
so it cannot see the external overlay's digest pin — the anti-`:latest`/anti-phantom guards do not
extend to Inception's image ref. (The `cybernetic-genesis` repo has its own self-contained check,
`tools/verify_deploy_self_contained.py`.)

> **Open question 1 (reviewer):** accept the external-repo source, or **vendor** the Inception
> kustomize base into prophet-platform (repoURL = self) so the estate preflight walks its digest pin
> too? Vendoring restores full contract coverage at the cost of a second copy that can drift from the
> upstream repo.

### D2 — Held / manual first sync (deviation from automated norm)

The Application ships with **no `automated:` block** and **no `CreateNamespace`**. Rationale: the
`inception` namespace does not exist on the cluster (validation ran in `inception-validation`, since
torn down), and the live-traffic posture is a held, owner-only decision. Automated sync + namespace
creation on an unmerged-but-later-merged manifest could adopt the service before the owner is ready.
So first sync is manual and the namespace is owner-provisioned. The target overlay is replicas 1, no
ingress, no traffic.

> **Open question 2 (reviewer):** on merge, flip to the estate norm `automated:{prune,selfHeal}` +
> `CreateNamespace=true`, or keep the manual/held gate until you explicitly cut over?

### D3 — tier = reference

Inception is a new runtime service, not part of the interoperability spine, and it is built by its own
repo's `image.yml`, **not** prophet-platform's `images.yml`. Check 6 requires `foundation` images be
rebuildable *here*; `reference` is the correct, passing claim. (`preflight_deploy_contract.py` exits 0
with this manifest added; `inception` raises no new finding.)

## Consequences

- **Reversible & inert.** Merging wires the manifest into the watched tree but, with no `automated`
  block, nothing syncs until an owner acts. Reverting is a file delete.
- **Digest-pinned.** No moving tag reaches a node cache; a re-pin is a one-line overlay edit in
  `cybernetic-genesis`.

## Blocker (owner IAM — NOT in scope of this ADR/PR)

The build side (`cybernetic-genesis/.github/workflows/image.yml`) authenticates to GAR via WIF using
secret names `GCP_WORKLOAD_IDENTITY_PROVIDER` / `GCP_SERVICE_ACCOUNT`. Those are today **repo-level on
prophet-platform**; there are **no org-level Actions secrets**, and `cybernetic-genesis` has none. A
WIF attribute binding admitting the `SocioProphet/cybernetic-genesis` OIDC subject to that service
account (with `roles/artifactregistry.writer` on the `socioprophet` GAR repo) does not yet exist. This
does not block the ArgoCD Application (it pulls the already-promoted, validated digest), but it does
block *future* image builds from that repo. Owner action, out of band.
