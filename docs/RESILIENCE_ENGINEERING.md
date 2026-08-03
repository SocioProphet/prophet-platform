# Resilience Engineering — deploy-time failure classes and the layered gates that close them

Status: Phase 1 (L1 + L2), Phase 2 (L3 + L5), and Phase 3 (L4 + L6) shipped. L4
(evidence-reference verification, INV-DEP-13) is shipped; L6 (auto-remediation) is shipped for the
RENAME case (`--fix` rewrites the unambiguous old→new references; deletions remain human judgment).
The cross-cutting gate registry (never-fired == suspect) is shipped: every gate must prove it can
fire. **L1–L6 and the meta-gate are all live.**

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
| **L4** | **Evidence-ref verification (INV-DEP-13).** Every claim a release/evidence artifact makes must resolve to real evidence, not a string that looks right — extend the "reference resolves" discipline from cluster objects to the EVIDENCE surface under `releases/`. Every repo-path ref (paths, lock refs, validation-record refs) must exist + parse; every `evidence://`/`file://` URI must resolve; every digest-evidence claim (`bundle_digest`/`rulepack_digest`) must equal `sha256(the file it names)`. `make evidence-refs-check`. | **shipped** |
| **L5** | **Local == CI parity (`make preflight`).** One target runs the fast, hermetic required-matrix legs locally (validate-repo, drift/standards/topology, the INV-DEP-9/10/11/12 gates, tools tests) so path-breaks and gate failures surface before push, not after. Opt-in `.githooks/pre-push` runs it. Infra-heavy legs (kind, go, docker) stay CI-only. | **shipped** |
| **L6** | **Auto-remediation.** When a derived gate KNOWS the mechanical fix, offer the patch, not just the refusal. Shipped for the RENAME case of the blast-radius gate (INV-DEP-12): a rename reports its git-detected target, so each surviving reference gets a concrete "→ `<new path>`" suggestion, and `verify_no_dangling_path_refs.py --fix` rewrites the unambiguous full-path references in place. DELETIONS have no safe target and are never auto-rewritten (human judgment). `--fix` is a developer convenience — CI stays report-only, fail-closed. | **shipped (rename); deletion = human judgment** |
| **meta** | **Gate registry — never-fired == suspect (cross-cutting).** `tools/gate_registry.yaml` registers every gate with the teeth-test that proves it can DENY; `tools/check_gate_registry.py` fails closed if a registered gate has no negative-case test, and — the ratchet — if any `tools/verify_*.py` is neither registered with teeth nor booked as explicit debt under `known_unproven`. On first run it surfaced 3 estate gates with no teeth (fogstack signature ×2, probe-contract), now booked as acknowledged debt. A new gate cannot land without proving it fires or being visibly recorded as debt. | **shipped** |

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
| **INV-DEP-12** | A refactor (move/rename/delete) → no surviving tracked reference to the OLD repo path | consumer dereferences a path that no longer exists (validator RED after push) | `tools/verify_no_dangling_path_refs.py` (`--fix` for renames) |
| **INV-DEP-13** | A release/evidence artifact → every repo-path / `evidence://` / digest-evidence claim resolves to a real, well-formed file | a fabricated `evidence://` URI or placeholder digest that "validates" green but resolves to nothing | `tools/verify_evidence_refs.py` |
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

## Runbook — the shipped Phase 2 + Phase 3 gates

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
- **Testable seam.** The core is `scan(removed_paths, tree_files, renames=None)` — pure, git-free,
  unit-tested both ways in `tools/tests/test_verify_no_dangling_path_refs.py`.
- **Auto-remediation (L6, rename case).** When the removed path is a **rename** (git reports the
  new target via `--diff-filter=R -M`), each surviving reference carries a concrete suggestion
  "→ `<new path>`", and `--fix` rewrites the **unambiguous full-path** references in place
  (`old` → `new`, on the same path boundaries) and prints a summary:

  ```
  python3 tools/verify_no_dangling_path_refs.py --fix   # rewrites rename cases, reports the rest
  ```

  **Deletions are never auto-rewritten** — a deleted path has no safe target to point at, so it is
  reported (no suggestion) and remains human judgment. A **bare-suffix** reference to a renamed
  path (e.g. `base/pvc.yaml` on its own) is likewise ambiguous to rewrite, so `--fix` reports it
  but leaves it for a human. `--fix` is a **developer convenience — CI never runs it**; the CI leg
  stays report-only and fail-closed. The default (no `--fix`) behaviour is unchanged: it reports
  and exits non-zero, modifying nothing.

## L4 — `make evidence-refs-check` (INV-DEP-13)

Evidence-reference verification. Extends "a reference must resolve" from cluster objects
(INV-DEP-9/10) and repo paths (INV-DEP-12) to the **evidence surface** under `releases/`
(`releases/manifests/*.json`, `releases/evidence/*.json`, `releases/images/*image-lock*.json`).
Every reference an artifact makes must prove itself, not merely pass schema shape.

- **The ghost it prevents.** A claim that looks right but resolves to nothing: a fabricated
  `evidence://` URI that "validated" (agent-registry #56), a placeholder digest rendered green.
  Schema-shape is necessary but never sufficient.
- **What it resolves.** (1) **Repo-path refs** — a whitespace-free string with ≥ 2 `/`-segments
  whose first segment is a real top-level repo entry MUST exist; a `.json`/`.yaml` target must also
  parse. (2) **`evidence://`/`file://` URIs** — the scheme is stripped and the target resolved.
  (3) **Digest-evidence** — a `<name>_digest` field whose sibling `<name>` names an existing repo
  file is verified by content: `sha256(file)` must equal the claimed digest (`bundle_digest`,
  `rulepack_digest`). Image digests (`digest`, `pinned_ref`, `source_content_digest`) name registry
  blobs, not repo files, and are covered by INV-DEP-6/7 — this gate does not touch them.
- **Deny-closed, no false positives.** Prose that merely contains a slash, a registry ref
  (`us-central1-docker.pkg.dev/…`), and an org/repo (`SocioProphet/prophet-platform`) are not
  repo-path refs and are left alone. An explicit `REPLACE_WITH_…`/`PLACEHOLDER` string in an
  `*.example.*` / `*.template.*` artifact is an unfilled slot, not a live claim — the ghost is a
  placeholder shaped like a REAL ref, which still fails, while templates stay green.
- **Testable seam.** The core is `scan(manifest_obj, resolver)` — pure over a `Resolver` boundary,
  unit-tested both ways in `tools/tests/test_verify_evidence_refs.py` (a resolvable ref passes; a
  missing file, a digest mismatch, and a fabricated `evidence://` URI each fail; a placeholder is
  skipped; the shipped `releases/` artifacts pass). Pure-filesystem: no kubectl, no cluster.

## L5 — `make preflight` (local == CI parity)

Runs the fast, hermetic subset of the required `validate-target-diagnostics` matrix locally, in
minutes, so a developer catches path-breaks and gate failures **before** pushing. Each leg is the
same `make` target CI runs, so a green preflight predicts a green matrix for those legs.

```
make preflight
```

Included legs: `validate-repo`, `drift-check`, `standards-check`, `topology-check`,
`rollout-analysis-refs-check`, `overlay-self-contained-check`, `manifest-completeness-check`,
`no-dangling-path-refs-check`, `evidence-refs-check`, `test-tools`. It prints a PASS / what-to-fix
summary and exits non-zero if any leg fails.

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
