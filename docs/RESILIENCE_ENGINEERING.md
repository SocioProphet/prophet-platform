# Resilience Engineering — deploy-time failure classes and the layered gates that close them

Status: Phase 1 (L1 + L2) and Phase 2 (L3 + L5) shipped. L4, L6, and the cross-cutting
last-fired gate registry are declared, not yet built.

## The failure class we are automating away

On 2026-08-02 a prod blue-green deploy repeatedly reached the cluster with manifests that
`kubectl kustomize` rendered **green** but the LIVE cluster rejected at **create / spec-admission
time** — a class of defect that dry-run rendering structurally cannot see, because it is about
whether *references resolve against the running cluster*, not about whether YAML is well-formed:

- An overlay referenced a `ServiceAccount` / `ConfigMap` / `PVC` it never rendered
  → `FailedCreate: serviceaccount not found`, **0 pods**.
- A Rollout referenced a **namespaced** `AnalysisTemplate` not in its namespace
  → `InvalidSpec: AnalysisTemplate not found`, **Degraded**.
- A placeholder / floating image reference
  → `ImagePullBackOff`.

Every one was caught **only by the real apply**. "Dry-run green, apply red" is the signature.

## The layered plan

The strategy is two-pronged and defence-in-depth: **derive** the references statically so a whole
*class* is caught without hand-writing a gate per type (cheap, fast, every PR), and **apply for
real** on an ephemeral cluster so the ground truth — "does the live API accept this?" — is a
continuous gate, not a thing we learn in prod.

| Layer | What | Status |
|---|---|---|
| **L1** | **Ephemeral real-apply preflight.** Stand up a hermetic `kind` cluster, install argo-rollouts CRDs + controller, ACTUALLY apply each promote overlay to a throwaway namespace, and assert the create/spec failure class does not occur. The effect-canary as a continuous gate. | **shipped** |
| **L2** | **Derived reference completeness (INV-DEP-11).** One checker that derives and resolves the reference types the point-gates do NOT cover (Secrets, image digest-pinning), so a novel ref type can't reach prod before someone hand-writes a gate for it. | **shipped** |
| **L3** | **Blast-radius-on-refactor (INV-DEP-12).** A git-diff-aware gate: when a PR deletes or renames a path, fail if any tracked file still references the old path — the exact break that moving `base/configmap.yaml` → `base-support/` caused (the academy-deploy validator hardcoded the old path). `make no-dangling-path-refs-check`. | **shipped** |
| L4 | **Evidence-ref verification.** Every claim a gate makes (a digest exists, a series is present, a receipt is sealed) must resolve to real evidence, not a string that looks right — extend the "reference resolves" discipline from cluster objects to evidence artifacts. | future |
| **L5** | **Local == CI parity (`make preflight`).** One target runs the fast, hermetic required-matrix legs locally (validate-repo, drift/standards/topology, the INV-DEP-9/10/11/12 gates, tools tests) so path-breaks and gate failures surface before push, not after. Opt-in `.githooks/pre-push` runs it. Infra-heavy legs (kind, go, docker) stay CI-only. | **shipped** |
| L6 | **Auto-remediation.** When a derived gate knows the fix (render the missing SA, pin the floating tag), offer/produce the patch, not just the refusal. | future |
| — | **Last-fired gate registry (cross-cutting).** A control that has never fired is suspect. Every gate here records when it last actually FAILED on something (the negative fixtures included), so a gate that has only ever passed is flagged for an adversarial review rather than trusted. L1's negative fixture is the first entry. | future |

## How the invariants + ephemeral-apply map onto it

The `INV-DEP-*` family (canonical: `docs/standards/deploy-wave-invariants-v0.md`) is the static half;
ephemeral-apply is the live half. They are complementary, not redundant — each INV-DEP-N is a
*derivation* that says "here is a reference class; prove every instance resolves in the rendered
set", and L1 is the *proof by construction* that the live API agrees.

| Gate | Reference class it resolves | Signal it prevents | Where |
|---|---|---|---|
| **INV-DEP-6** | Every promoted digest exists in the registry the nodes pull from | `ErrImagePull: manifest unknown` | `tools/verify_pinned_digest_exists.py` |
| **INV-DEP-9** | Rollout → AnalysisTemplate (namespaced) / ClusterAnalysisTemplate (clusterScope) | `InvalidSpec: AnalysisTemplate not found` (Degraded) | `tools/verify_rollout_analysis_refs.py` |
| **INV-DEP-10** | Workload → ServiceAccount / ConfigMap / PVC rendered in-overlay | `FailedCreate: serviceaccount not found` (0 pods) | `tools/verify_overlay_self_contained.py` |
| **INV-DEP-11** | Workload → Secret (rendered or allowlisted) **+** every image digest-pinned | `secret not found` (FailedMount) / `ImagePullBackOff` (placeholder/floating) | `tools/verify_manifest_completeness.py` |
| **ephemeral-apply (L1)** | ALL of the above, proven against a live API server, not derived | any create/spec-time rejection | `.github/workflows/ephemeral-apply-preflight.yml` + `.github/app-ci/ephemeral-apply-assert.sh` |

INV-DEP-9/10 are **point gates**: each was written after an incident named its one reference type.
INV-DEP-11 is **derived** — it closes the reference classes 9/10 do not cover (Secrets, image
pinning) in one checker, so the *next* novel ref type is caught by the derivation rather than by the
next incident. L1 is the backstop under all of them: it renders and applies for real, so a reference
class nobody has thought to derive yet still fails the moment the live cluster rejects it.

### Never-fired == suspect

Every gate here is proven **both ways**. INV-DEP-9/10/11 each ship teeth in `tools/tests/` that feed
a resolvable overlay (must pass) and a dangling ref (must fail). L1 carries a negative fixture,
`infra/k8s/search-orchestrator/overlays/_selftest-broken/` — a Rollout naming a ServiceAccount the
overlay does not render — and the workflow applies ONLY that fixture and fails the job unless the
detector reports the `FailedCreate` (returns non-zero). A gate that has only ever passed proves
nothing; the fixture is the standing proof that this one can still fail.

## Runbook — the shipped Phase 2 gates

## L3 — `make no-dangling-path-refs-check` (INV-DEP-12)

Blast-radius on refactor. A git-diff-aware gate: it computes the paths a PR **deleted or
renamed-away** (`git diff --diff-filter=DR` against the merge-base with `origin/main`) and fails
if any surviving tracked file still references one of those old paths.

- **The incident it prevents.** `infra/k8s/search-orchestrator/base/configmap.yaml` was correctly
  factored out to `.../base-support/configmap.yaml`, but
  `tools/validate_search_orchestrator_academy_deploy.py` had the old `base/` path hard-coded. The
  move was invisible to that consumer; the validator only went red in CI, after push. This gate
  catches that shape in the diff.
- **No false positives.** It matches the full old path or a path suffix of ≥ 2 segments
  (`base/configmap.yaml`), on path boundaries — never a bare shared basename like
  `kustomization.yaml`, which unrelated files legitimately share.
- **Fail-closed.** If git is unavailable or the diff cannot be computed, it exits non-zero. In CI
  it needs full history, so its matrix leg checks out with `fetch-depth: 0`.
- **Testable seam.** The core is `scan(removed_paths, tree_files)` — pure, git-free, unit-tested
  both ways in `tools/tests/test_verify_no_dangling_path_refs.py`.

## L5 — `make preflight` (local == CI parity)

Runs the fast, hermetic subset of the required `validate-target-diagnostics` matrix locally, in
minutes, so a developer catches path-breaks and gate failures **before** pushing. Each leg is the
same `make` target CI runs, so a green preflight predicts a green matrix for those legs.

```
make preflight
```

Included legs: `validate-repo`, `drift-check`, `standards-check`, `topology-check`,
`rollout-analysis-refs-check`, `overlay-self-contained-check`, `no-dangling-path-refs-check`,
`test-tools`. It prints a PASS / what-to-fix summary and exits non-zero if any leg fails.

**Deliberately excluded** (they stay in CI, never in preflight): the L1 real-apply / digest-exists
preflight and the `wave-promote` GATE chain (need registry/cluster credentials); `kind`,
`test-go`, the per-app venv suites (`app-test-diagnostics`), `docker`, and the smoke matrix. These
are infra-heavy or non-hermetic — running them on a laptop would make preflight slow and flaky,
defeating its purpose. They remain fully covered by the required CI matrix.

### Opt into the pre-push hook

`.githooks/pre-push` runs `make preflight` before every push. It is **not** auto-installed; opt in
per clone:

```
git config core.hooksPath .githooks
```

Bypass for a single push (e.g. a deliberate WIP branch) with `git push --no-verify`.
