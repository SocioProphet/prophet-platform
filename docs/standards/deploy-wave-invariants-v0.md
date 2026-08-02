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
