# Standard: Deploy-Wave Invariants v0 (build-once-promote-many)

Status: **v0 (normative)** · Scope: prophet-platform deployment automation · Owner:
prophet-platform · Enforced by: the tools/gates named per invariant.

> Recorded here (`docs/standards/`) because a dedicated `prophet-platform-standards` repo is
> not present in this checkout. If that repo exists, this file is the source to lift into it.

These invariants govern how a built artifact reaches a cluster. Each is stated normatively and
names the **mechanism that makes it fail-closed** — a standard nothing enforces is a wish.

---

## INV-DEP-1 — Digest-pin only (no moving tags / IfNotPresent)

Every deployed container image MUST be referenced by an immutable digest
(`<image>@sha256:<64hex>`). A moving tag (`:latest`, `:main`, `:dev`, `:sha-…`) MUST NOT
appear in any desired-state manifest, image-lock, or frozen release manifest.

*Rationale.* `imagePullPolicy: IfNotPresent` + a moving tag means a node that cached the tag
never pulls the fix — the update silently never rolls (estate memory; the 2-day crashloop
behind a green pipeline).

*Enforced by.* `tools/preflight_deploy_contract.py` (rejects `tag: latest`);
`freeze_release_train_manifest.py` + `validate_release_train_manifest.py` (refuse a non-digest
`pinned_ref`); `wave-promote.yml`'s "assert digest-pinned" render gate.

## INV-DEP-2 — Build-once-promote-many (no per-wave rebuild)

An artifact promoted through waves MUST be the SAME immutable digest at every wave. A
component MUST NOT be rebuilt to advance a wave, and a frozen release manifest MUST NOT contain
one image at two digests.

*Enforced by.* `apply_wave_promotion.py` writes the frozen digest verbatim into each wave
overlay (it has no build path); `validate_release_train_manifest.py` fails a manifest with two
digests for one image (`test_validate_refuses_two_digests_for_one_image`); the dry-run proves
dev/canary/prod render an identical `sha256:`.

## INV-DEP-3 — Wave order + a fail-closed gate between waves

Promotion MUST proceed dev → canary → prod. A later wave MUST NOT start until the earlier wave
is healthy AND the between-wave gates pass. The gates MUST be fail-closed: absent data / a
skipped check counts as FAILURE, never success. Prod cutover MUST be blue-green and
SLO-gated (`prePromotionAnalysis: slo-gate`, `autoPromotionEnabled: false`).

*Enforced by.* `release-train.yml` `needs:` chaining + ArgoCD `sync-wave` (20/21/22);
`wave-promote.yml` runs `preflight_deploy_contract.py` + `check_canary_slo_gate.py` and, for
prod, asserts the slo-gate + gated cutover; `analysistemplate-slo.yaml` requires
`len(result) > 0` to succeed and fires on an empty series.

## INV-DEP-4 — Scheduled release train (no deploy-per-merge to prod)

Production deploys MUST happen on the release train (`schedule` / `release` tag / operator
`dispatch`), driving a FROZEN digest set. A merge to main MUST NOT, by itself, promote to prod.

*Enforced by.* `release-train.yml` is the only path that promotes to the prod wave; its freeze
job snapshots the digest set before any wave runs; `images.yml`/`gitops-promote.yml` update
build pins but do not cut prod.

## INV-DEP-5 — Cost discipline

- An **unchanged** component MUST rebuild **zero** times: a preflight compares the source
  content-digest to the recorded lock and skips the build on a match.
- **Release** builds (main) MUST **queue** (`cancel-in-progress: false`) so every built image
  reaches the registry.
- **Feature/PR** builds MUST **cancel** superseded runs (`cancel-in-progress: true`) to save
  runner minutes.

*Enforced by.* `tools/compute_source_content_digest.py` (skip decision, unit-tested both ways);
the `concurrency.cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}` block in each
per-component image workflow; `type=gha` scoped layer cache;
`test_image_workflows_queue_on_main_cancel_on_feature` / `test_release_and_wave_workflows_never_cancel`.

## INV-DEP-6 — A promoted digest MUST exist in the registry

A digest MUST NOT be frozen or promoted unless it resolves to a real manifest in its registry
(Registry HTTP API v2 `HEAD`/`GET …/manifests/<digest>` returns the manifest). "Digest-shaped"
(INV-DEP-1) and "one digest per image" (INV-DEP-2) are necessary but NOT sufficient: a
never-pushed placeholder is a perfectly-shaped `sha256:<64hex>` that `ImagePullBackOff`s on the
cluster. A **skip** is likewise only safe if the recorded digest still exists — an unchanged
source that "reuses" a phantom digest is the same failure via the cost guard.

*Rationale.* A wave-deploy froze + promoted `search-orchestrator@sha256:bbfea6e4…` through every
overlay — every shape/ordering gate green — and it `ImagePullBackOff`'d on the live cluster
because Wave 0 (the real build+push) never ran. Every prior gate checked the *shape* of the
reference; none checked that the bytes it names EXIST.

*Fail-closed distinction.* The check returns three DISTINCT outcomes — EXISTS (pass), ABSENT
(registry answered 404/`MANIFEST_UNKNOWN` — the fabricated/never-pushed case), and UNREACHABLE
(DNS/TLS/timeout/5xx/auth-challenge-unsatisfiable). Both ABSENT and UNREACHABLE FAIL the gate
(existence was not proven), but they are reported distinctly so an operator is never told
"fabricated digest" when the real problem is reachability.

*Enforced by.* `tools/verify_pinned_digest_exists.py` (unit-tested both ways, `check_manifest`);
`release-train.yml`'s freeze step and `wave-promote.yml`'s GATE 0b both call it and REFUSE to
freeze/promote a digest with no manifest; `compute_source_content_digest.py decide
--verify-image-exists` forces BUILD when a source-matched lock's pinned digest is missing
(`test_decide_build_when_source_matches_but_image_missing`).

## INV-DEP-7 — A lock digest is only ever a real push output

The `digest` recorded in a `releases/images/<component>.image-lock.json` MUST come from an actual
`docker buildx …--push` (the registry's own content digest, `steps.build.outputs.digest`). It is
NEVER hand-authored and NEVER *computed*. The image build workflow — via its digest-evidence
artifact — is the SOLE writer of the lock's `digest`; the applier stamps `digest_provenance:
buildx-push` and refuses evidence whose digest is empty or a placeholder sentinel. A lock without
that provenance, or carrying a `source_content_digest` divorced from a real push, is illegitimate.

*Rationale.* The `bbfea6e4…` incident began as a lock whose `digest` (and its neighbouring
`source_content_digest`) were entered by hand, with no push behind either. Making the build the
only writer removes the class of failure at the source: there is no code path that puts a
non-push digest into a lock.

*Enforced by.* `tools/apply_search_orchestrator_image_lock.py` (sole lock writer; refuses a
non-`sha256:<64hex>` / placeholder evidence digest, carries the build's `source_content_digest`,
stamps `digest_provenance`) — `test_build_lock_refuses_placeholder_digest`,
`test_build_lock_carries_source_content_digest_from_the_same_build`; INV-DEP-6 catches any lock
digest that slips through and does not actually exist.

## INV-DEP-8 — The pinned registry MUST be one the target nodes can pull from

A digest-pinned ref MUST name a registry the deploying cluster is authorized to pull from. For
GKE that is **GCP Artifact Registry** (`us-central1-docker.pkg.dev/socioprophet-platform/socioprophet`,
WIF-authed) or the sovereign zot (`registry.socioprophet.ai`) — **never ghcr**, which the GKE
nodes have no credential for. INV-DEP-6 proves the bytes exist in *some* registry; INV-DEP-8
proves they exist in *the one the nodes can reach*. Both must hold: a digest that a public HEAD
resolves but the cluster cannot pull still `ImagePull`s at apply.

*Rationale.* The 2026-08-02 apply-caught incident: the wave-deploy plane built+pinned+promoted
`ghcr.io/socioprophet/prophet-platform/search-orchestrator`. Every shape/existence gate passed
(the public ghcr digest even resolved EXISTS), yet the real `fogstack-federal` apply `401`'d —
the nodes pull `search-orchestrator` from GAR and hold no ghcr auth. A registry mismatch that
only a real apply, not dry-run, surfaces.

*Enforced by.* `tools/preflight_deploy_contract.py` (`OUR_REGISTRIES` = GAR + zot; a first-party
image ref pointing at ghcr is flagged `wrong-registry` in CI, not just at apply). The build path
(`search-orchestrator-image.yml`) pushes to GAR via `google-github-actions/auth` WIF, and
`verify_pinned_digest_exists.py` authenticates GAR HEADs with the WIF access token
(`GAR_ACCESS_TOKEN`) so INV-DEP-6 verifies against the registry the nodes actually use.

## INV-DEP-9 — An overlay MUST be self-contained: every referenced cluster resource is rendered by the overlay or is cluster-scoped

A workload in an overlay MUST NOT reference a **namespaced** cluster resource that the overlay
does not itself render. Specifically for Argo Rollouts: an `AnalysisTemplate` is namespaced, so a
Rollout may reference it ONLY if the overlay renders an `AnalysisTemplate` of that name into the
SAME namespace; otherwise the reference MUST be to a cluster-scoped `ClusterAnalysisTemplate`
(with `clusterScope: true`), which resolves from any namespace. The estate's shared SLO gate is
therefore a **`ClusterAnalysisTemplate` `slo-gate`** (`infra/k8s/rollouts/base/analysistemplate-slo.yaml`),
applied once cluster-wide and referenced `clusterScope: true` by every wave Rollout — one
definition, no per-namespace copy to drift.

*Rationale.* The wave-deploy prod blue-green Rollout referenced `slo-gate`, but that
`AnalysisTemplate` existed ONLY in the `socioprophet` namespace. `kubectl kustomize` rendered the
prod overlay perfectly and every shape/existence gate (INV-DEP-1/2/6/8) passed — yet deploying it
to a fresh `prophet-platform-prod` namespace failed on the LIVE Rollout controller with
`InvalidSpec: AnalysisTemplate 'slo-gate' not found` (Degraded, **no pods**). A namespaced
cross-namespace reference is invisible to a dry-run render; only a real apply surfaces it — the
same "dry-run green, apply red" class as INV-DEP-6/8, now for a *namespaced-resource* reference
rather than an image.

*Fail-closed distinction.* The check renders each overlay and classifies every Rollout analysis
ref: RESOLVED (a namespaced ref whose template the overlay renders, OR a clusterScope ref whose
`ClusterAnalysisTemplate` the repo declares) vs DANGLING (neither). A DANGLING ref FAILS. A render
that will not `kubectl kustomize`, or output that will not parse, also FAILS — an overlay that
cannot be certified self-contained is treated as not self-contained.

*Enforced by.* `tools/verify_rollout_analysis_refs.py` (renders the promote overlays; proven both
ways by `tools/tests/test_verify_rollout_analysis_refs.py` — a resolvable overlay passes, a
dangling namespaced ref and an undeclared-clusterScope ref both fail); `make
rollout-analysis-refs-check` in the required `validate-target-diagnostics` matrix;
`wave-promote.yml` GATE 3b renders the promoting wave's overlay and refuses a dangling ref before
any apply.

---

## INV-DEP-12 — A refactor MUST NOT leave a dangling repo-path reference (blast-radius on move/rename/delete)

A PR that MOVES, RENAMES, or DELETES a repo path MUST NOT leave any surviving tracked file still
referencing that path by its **old** name. A hard-coded path is just a string: renaming the file
it points at does not touch the string, so the reference silently rots. Nothing in the diff of
the *moved* file can reveal the break — it only surfaces when something dereferences the path at
run time. This is the same "renders/parses clean, fails on use" class as INV-DEP-9 (a namespaced
cluster ref), lifted to *repo-path* references.

*Rationale.* `infra/k8s/search-orchestrator/base/configmap.yaml` was correctly factored out to
`.../base-support/configmap.yaml` so the prod blue-green overlay could render it. But
`tools/validate_search_orchestrator_academy_deploy.py` had the old `.../base/configmap.yaml`
path hard-coded in its required-files list. The move was invisible to that consumer; the
validator only went RED in CI, AFTER push. A diff-time gate would have caught it before the push
(and `make preflight`, L5, runs it locally).

*Fail-closed / no-false-positive distinction.* The check computes the paths deleted or
renamed-away between HEAD and the merge-base with `origin/main`, then searches the CURRENT tree
(tracked files only) for a surviving literal reference to each old path — matching the full path
OR a path suffix of ≥ 2 segments (e.g. `base/configmap.yaml`), on path boundaries, and NEVER a
bare shared basename (`kustomization.yaml`) which two unrelated files can legitimately share. A
surviving reference to a now-missing path FAILS with `file:line` and the missing path. If git is
unavailable, or the merge-base / diff cannot be computed, the gate FAILS — a gate that cannot
compute blast-radius must not pass. (In CI this needs full history: check out with
`fetch-depth: 0`.)

*Enforced by.* `tools/verify_no_dangling_path_refs.py` (pure `scan()` seam, proven both ways by
`tools/tests/test_verify_no_dangling_path_refs.py` — a still-referenced removed path fails, an
all-references-updated rename and a bare-basename collision are both clean); `make
no-dangling-path-refs-check` in the required `validate-target-diagnostics` matrix (with
`fetch-depth: 0`); and locally via `make preflight`. See also `docs/RESILIENCE_ENGINEERING.md`.

---

## Conformance checklist

| # | Check | Command |
|---|---|---|
| 1 | Frozen manifest is digest-pinned, one digest/image | `python3 tools/validate_release_train_manifest.py releases/manifests/release-train.<label>.manifest.json` |
| 2 | No moving tag in desired state | `python3 tools/preflight_deploy_contract.py` |
| 3 | Canary gate fails closed on no data | `python3 tools/check_canary_slo_gate.py` |
| 4 | Overlays render, all `@sha256:` | `kubectl kustomize infra/k8s/search-orchestrator/overlays/promote/{dev,canary,prod}` |
| 5 | Skip + queue/cancel contract | `python3 -m pytest -q tools/tests/test_compute_source_content_digest.py tools/tests/test_release_train_manifest.py` |
| 6 | Workflows lint | `actionlint .github/workflows/{release-train,wave-promote,*-image}.yml` |
| 7 | Every frozen digest exists in the registry (INV-DEP-6) — GAR needs a WIF token | `GAR_ACCESS_TOKEN="$(gcloud auth print-access-token)" python3 tools/verify_pinned_digest_exists.py manifest releases/manifests/release-train.<label>.manifest.json` |
| 8 | Digest-exists (incl. GAR) + lock-provenance gates, both ways (INV-DEP-6/7) | `python3 -m pytest -q tools/tests/test_verify_pinned_digest_exists.py tools/tests/test_apply_search_orchestrator_image_lock.py` |
| 9 | First-party refs point at a pullable registry — GAR/zot, not ghcr (INV-DEP-8) | `python3 tools/preflight_deploy_contract.py` |
| 10 | Overlays self-contained — every Rollout analysis ref resolves (INV-DEP-9) | `python3 tools/verify_rollout_analysis_refs.py` (+ `python3 -m pytest -q tools/tests/test_verify_rollout_analysis_refs.py`) |
| 11 | Workloads self-contained — every SA/ConfigMap/PVC a pod names is rendered (INV-DEP-10) | `python3 tools/verify_overlay_self_contained.py` (+ `python3 -m pytest -q tools/tests/test_verify_overlay_self_contained.py`) |
| 12 | Workloads complete — every Secret rendered/allowlisted + every image digest-pinned (INV-DEP-11) | `python3 tools/verify_manifest_completeness.py` (+ `python3 -m pytest -q tools/tests/test_verify_manifest_completeness.py`) |
| 13 | No dangling repo-path reference after a move/rename/delete (INV-DEP-12) | `python3 tools/verify_no_dangling_path_refs.py` (+ `python3 -m pytest -q tools/tests/test_verify_no_dangling_path_refs.py`) |
| 14 | Local == CI parity: the fast required matrix, run locally (L5) | `make preflight` |
