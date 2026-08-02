# Wave-based deploy — build-once, promote-many

The estate's deployment automation: build each component's image **once**, record its
immutable `sha256:` digest, and **promote that same digest** through env waves
(dev → canary → prod) on a **scheduled release train** — never rebuilding downstream, never
deploying per-merge to prod. This builds on the machinery already in the repo (`images.yml`,
`gitops-promote.yml`, `preflight-deploy-contract`, the Argo Rollouts `slo-gate`, the ArgoCD
appset sync-waves, `releases/images/*.image-lock.json`); it does not replace it.

The normative invariants are in
[`docs/standards/deploy-wave-invariants-v0.md`](standards/deploy-wave-invariants-v0.md)
(INV-DEP-1…7). This doc is the operator/design narrative.

---

## Why (the failure this closes)

Two estate rules converge here:

1. **`:latest` + `IfNotPresent` never rolls** (memory / `preflight_deploy_contract.py`): a
   moving tag with `imagePullPolicy: IfNotPresent` means a node that cached the tag never
   pulls the fix. **Only an immutable digest rolls deterministically.**
2. **Deploys drifted from builds** (the incident `gitops-promote.yml` was written for):
   `images.yml` built `sha-<commit>` on every merge but nothing advanced the deployed pins.
3. **A frozen digest that was never pushed** (the wave-deploy incident, INV-DEP-6/7): a lock
   recorded `search-orchestrator@sha256:bbfea6e4…` with a matching `source_content_digest`, both
   entered by hand — Wave 0 never built or pushed it. Every shape/ordering gate passed; the
   apply `ImagePullBackOff`'d on the live cluster, and the cost guard would have *skipped* the
   real build forever because the recorded content-digest matched the source. **A digest-pinned
   reference is only trustworthy if the bytes it names exist and came from a real push.**

Build-once-promote-many answers all three: the thing that moves between environments is an
**immutable digest**, it moves on a **train**, gated, not on every merge — and every freeze,
promote and skip is now fail-closed on the digest *actually existing* in the registry
(INV-DEP-6), with the build workflow the only writer of a lock digest (INV-DEP-7).

---

## The pipeline

```
                          ┌──────────────────────── WAVE 0: BUILD ONCE ─────────────────────────┐
   source change ──▶ changes(cost guard 1) ──skip?──▶ reuse pinned digest                        │
                          │                     └─no─▶ build ▶ push (zot/GHCR/GAR) ▶ record digest │
                          │                                     releases/images/<c>.image-lock.json│
                          └──────────────────────────────────────────────────────────────────────┘
                                                        │  (immutable sha256:… + source_content_digest)
                                                        ▼
   release-train.yml ── FREEZE ──▶ releases/manifests/release-train.<label>.manifest.json
     (schedule / release tag / dispatch)      one digest per component (INV-DEP-2)
                                                        │
              ┌───────────────── promote-MANY (wave-promote.yml, NO rebuild) ─────────────────┐
              ▼                              ▼                                   ▼
        WAVE 1: dev                   WAVE 2: canary                        WAVE 3: prod
   overlays/promote/dev          overlays/promote/canary              overlays/promote/prod
   sync-wave 20                  sync-wave 21                         sync-wave 22 (blue-green)
   Deployment, digest-pinned     Deployment, digest-pinned           Rollout blueGreen, digest-pinned
              │  gate ▶                     │  gate ▶ slo-gate                 │  gate ▶ slo-gate
              └──── preflight + slo-gate fail-closed between every wave (INV-DEP-3) ───────────┘
                                                        │
                                              ArgoCD sync (Michael's gated apply)
```

Every wave carries the **identical** `sha256:`: the dev, canary and prod overlays all render the
same `…/search-orchestrator@sha256:…` digest — a wave re-pins, it never rebuilds. (Note: the
digest currently committed across the lock, frozen manifest and overlays,
`…@sha256:bbfea6e4a7ea432…`, is the never-pushed placeholder from the incident. It no longer
promotes: INV-DEP-6 refuses it at freeze and at every wave until a real Wave-0 push (see the
`gh workflow run` sequence below) replaces it with a digest that actually exists.)

---

## Wave 0 — build once → registry

Per-component image workflows (`socioprophet-api-image.yml`, `tritrpc-gateway-image.yml`,
`search-orchestrator-image.yml`) and the matrix `images.yml` build → push → record the
immutable digest in `releases/images/<component>.image-lock.json`.

**Target registry = GCP Artifact Registry (GAR), WIF-authed — NOT ghcr.** The estate's real
GKE registry is `us-central1-docker.pkg.dev/socioprophet-platform/socioprophet` (the default in
`images.yml`; the same path `helm-release.yml` pushes charts to). The GKE nodes hold Workload
Identity Federation auth to GAR and **none** to ghcr, so a ghcr digest — placeholder *or* real —
`401`s on pull at apply time. `search-orchestrator-image.yml` therefore authenticates with
`google-github-actions/auth` (WIF → access token) and `docker login us-central1-docker.pkg.dev -u
oauth2accesstoken`, mirroring the canonical pattern. (`registry.socioprophet.ai` / zot is the
sovereign registry the wider cutover moves to per-component; search-orchestrator is on GAR.)

> **Lesson — an apply-caught registry mismatch (2026-08-02).** The wave-deploy plane
> (#1225/#1226) built, pinned and promoted `ghcr.io/socioprophet/prophet-platform/search-orchestrator`.
> Every dry-run/CI gate was green — the ref is a legal `<image>@sha256:…`, the overlays render
> digest-pinned, INV-DEP-6 resolved the *public* ghcr digest as EXISTS. Only a **real cluster
> apply** surfaced it: `fogstack-federal` pulls `search-orchestrator` from **GAR** and the nodes
> have no ghcr credential, so the apply `401`'d on both the placeholder and the real ghcr digest.
> Dry-run "the digest exists in *a* registry" is not "the cluster can pull it from *this*
> registry." The registry the pin names must be the one the nodes are authorized to pull from —
> now asserted statically by `preflight_deploy_contract.py`'s `OUR_REGISTRIES` (GAR + zot, ghcr
> excluded) so a ghcr search-orchestrator ref fails CI, not just the apply.

**INV-DEP-7 — the build is the ONLY writer of a lock digest.** The lock's `digest` comes only
from a real `docker buildx …--push` (`steps.build.outputs.digest`), carried through the digest
evidence artifact and applied by `tools/apply_search_orchestrator_image_lock.py`, which stamps
`digest_provenance: buildx-push` and refuses a blank/placeholder evidence digest. A lock digest
is never hand-authored or computed — that is the class of failure the `bbfea6e4…` incident was.

To actually produce a real search-orchestrator digest (Wave 0), dispatch the build on `main`
(it WIF-auths to GAR, pushes `us-central1-docker.pkg.dev/socioprophet-platform/socioprophet/search-orchestrator:main`
+ `:sha-<commit>`, uploads the GAR digest evidence, and the pin workflow opens the lock PR that
propagates the digest into the policy + dev/canary/prod overlays):

```bash
# 1) Build + push to GAR via WIF, recording the REAL GAR digest (main only pushes; PRs build without push):
gh workflow run search-orchestrator-image.yml --ref main
# 2) After it succeeds, pin the lock + ALL overlays from that run's GAR digest evidence (auto-fires on
#    the build's success; run explicitly to pin a specific/older successful run):
gh workflow run search-orchestrator-image-pin.yml --ref main         # latest successful build
#    or:  gh workflow run search-orchestrator-image-pin.yml --ref main -f run_id=<BUILD_RUN_ID>
# 3) Verify the freshly-pinned GAR digest really resolves (the same gate the train runs). Locally,
#    supply a GAR access token so the private HEAD authenticates (CI's `changes` job does this via WIF):
GAR_ACCESS_TOKEN="$(gcloud auth print-access-token)" \
  python3 tools/verify_pinned_digest_exists.py locks 'releases/images/search-orchestrator.image-lock.json'
#    (Until step 1 runs, the committed lock still carries the retired ghcr push digest, which is
#     genuinely absent from GAR — INV-DEP-6 fails closed against it by design; the real push replaces it.)
```

- **COST GUARD 1 — change-detection skip (now image-exists-aware, INV-DEP-6).** A `changes`
  preflight job runs `tools/compute_source_content_digest.py decide --verify-image-exists`, which
  hashes the component's source paths into a `source_content_digest` and compares it to the value
  recorded in the image-lock **AND** confirms the recorded digest still resolves to a registry
  manifest. Byte-identical source **and** a real, present image ⇒ `build_needed=false` ⇒ the build
  is skipped and the already-pinned digest reused; a missing/unverifiable image forces BUILD even
  when the source matches (so a phantom digest can never win an eternal skip). Proven both ways —
  including "source matches but image missing ⇒ BUILD" — in
  `tools/tests/test_compute_source_content_digest.py`.
- **COST GUARD 2 — queue vs cancel.** `concurrency.cancel-in-progress:
  ${{ github.ref != 'refs/heads/main' }}` — main builds **queue** (never cancelled, so every
  built image reaches the registry and no pin dangles); feature/PR builds **cancel** superseded
  runs. Plus GitHub Actions layer cache (`type=gha`, per-image `scope`) so unchanged build
  stages are not re-run.

## Waves 1..N — promote the digest, no rebuild

`wave-promote.yml` (reusable) advances the SAME frozen digest through env overlays. It:
1. validates the frozen manifest (`validate_release_train_manifest.py`, fail-closed);
2. **asserts the promoted digest EXISTS in the registry** (`verify_pinned_digest_exists.py`,
   GATE 0b, INV-DEP-6) — a promotion of a non-existent digest is refused before any re-pin;
3. re-pins the digest into the wave's kustomize `image-patch.yaml`
   (`apply_wave_promotion.py`) — **no build**;
4. renders the overlay and asserts every image is `@sha256:…` (INV-DEP-1);
5. runs `preflight_deploy_contract.py` + `check_canary_slo_gate.py` (fail-closed);
6. for prod, asserts the blue-green `slo-gate` prePromotionAnalysis is present and the cutover
   is gated (`autoPromotionEnabled:false`).

The freeze step in `release-train.yml` runs the SAME INV-DEP-6 check on the whole frozen set
before any wave starts, so a phantom digest is refused at freeze, not just at promote.

Ordering is enforced twice: as GitHub `needs:` chaining in the train (dev → canary → prod),
and as ArgoCD `sync-wave` annotations (20/21/22) layered above the appset's existing
dependency waves (0…13).

## Blue-green at prod

`infra/k8s/search-orchestrator/overlays/promote/prod` renders an Argo Rollouts `Rollout`
(`strategy.blueGreen`), reusing the estate's existing fail-closed
`slo-gate` gate (`infra/k8s/rollouts/base/analysistemplate-slo.yaml`) as
`prePromotionAnalysis`:

- the frozen digest deploys to **GREEN** (`previewService: search-orchestrator-preview`);
- `slo-gate` runs against the preview — an **empty Prometheus series ABORTS** ("no data" ≠
  "healthy"), never promotes;
- cutover to **BLUE** (`activeService`) happens only after the gate passes
  (`autoPromotionEnabled: false`);
- the old ReplicaSet is retained `scaleDownDelaySeconds: 600` for **instant rollback** — flip
  the Service selector back, no rebuild, no re-pull.

> **Self-contained overlays — the apply-caught lesson (INV-DEP-9).** `slo-gate` is a
> **`ClusterAnalysisTemplate` (cluster-scoped)**, referenced `clusterScope: true`. It used to be a
> namespaced `AnalysisTemplate` in `socioprophet` — and `AnalysisTemplate`s are namespaced, so a
> Rollout only resolves one in its OWN namespace. The prod overlay deploys into a fresh
> `prophet-platform-prod` namespace that held no such template, so the LIVE Rollout controller
> rejected it: `InvalidSpec: AnalysisTemplate 'slo-gate' not found` (Degraded, **no pods**) — even
> though `kubectl kustomize` rendered clean and every shape/existence gate was green. Same
> "dry-run green, apply red" class as INV-DEP-6/8, now for a *namespaced-resource* reference. The
> rule an overlay must satisfy: **every cluster resource it references is either rendered by the
> overlay itself (namespaced, same namespace) or is cluster-scoped.** Enforced before any apply by
> `tools/verify_rollout_analysis_refs.py` (`make rollout-analysis-refs-check`; `wave-promote.yml`
> GATE 3b renders the promoting overlay and refuses a dangling analysis ref).

## Scheduled release train

`release-train.yml` (`on: schedule` Tue/Thu 09:00 UTC + `release: published` + `dispatch`):
1. **FREEZE** — `freeze_release_train_manifest.py` snapshots the exact digest set from the
   locks + inventory into `releases/manifests/release-train.<label>.manifest.json`;
2. **VALIDATE** — fail-closed against INV-DEP-1/2;
3. **PROMOTE** — calls `wave-promote.yml` per wave. A release tag ships to prod; the schedule
   stops at canary and waits for an operator to run the prod wave; dispatch takes the
   operator's `through_wave`.

Deploys ride the train, **not** each merge (INV-DEP-4).

---

## Cost model

| Lever | Mechanism | Saving |
|---|---|---|
| Unchanged component | COST GUARD 1 skip → 0 builds | full build+push avoided |
| Superseded feature build | `cancel-in-progress` on non-main | runner minutes on dead runs |
| Release build | `cancel-in-progress:false` → queue | correctness (no dangling pin) over speed |
| Repeated build stages | `type=gha` layer cache (scoped) | re-uses unchanged layers |
| Downstream waves | promote-many (re-pin only) | **N−1 rebuilds eliminated per release** |

The dominant saving is structural: a release of a component historically meant a build per
environment. Build-once-promote-many makes it **one** build and `N` cheap re-pins.

---

## What is dry-run vs what needs a live cluster

**Validated offline in this PR** (no cluster): `kubectl kustomize` renders all three promote
overlays with the identical digest and ascending sync-waves; the frozen manifest validates;
the skip/build decision (including "source matches but image missing ⇒ BUILD"), the digest-exists
gate (both ways), the lock-provenance guard and the queue-vs-cancel contract are unit-tested;
all workflows pass `actionlint` + `yaml.safe_load`; `preflight_deploy_contract.py` and
`check_canary_slo_gate.py` pass; `verify_rollout_analysis_refs.py` renders the promote overlays
and proves every Rollout analysis ref resolves (INV-DEP-9) — proven both ways, a planted dangling
ref fails the gate. The INV-DEP-6 gate is also proven live against a public registry:
a real `ghcr.io/oras-project/oras@sha256:0087224…` HEADs 200 ⇒ EXISTS (exit 0); a fabricated
digest on the same repo HEADs 404 ⇒ ABSENT (exit 4).

**Needs Michael's gated apply / CI credentials** (not done here): ArgoCD actually syncing the
promote overlays; the argo-rollouts controller + Gateway API plugin installed
(`deploy/argocd/progressive-delivery-services.yaml`); the blue-green cutover and `slo-gate`
querying real Prometheus series; and — the root cause — the per-component **registry push +
digest recording** actually running in CI (the `gh workflow run` sequence above) to replace the
`bbfea6e4…` placeholder with a real digest. Against the private repo without the CI token, the
INV-DEP-6 gate here reports UNREACHABLE (401) and still fails closed — it never passes on an
unverified image. Nothing here has been applied to any cluster.
