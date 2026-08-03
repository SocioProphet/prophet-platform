# Resilience Engineering — deploy-time failure classes and the layered gates that close them

Status: Phase 1 (L1 + L2) shipped. L3–L6 are declared, not yet built.

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
| L3 | **Blast-radius-on-refactor.** When a shared resource (a base, a ClusterAnalysisTemplate, a support kustomization) changes, compute which overlays/waves it affects and re-render/apply exactly those — refuse a refactor whose blast radius is unproven. | future |
| L4 | **Evidence-ref verification.** Every claim a gate makes (a digest exists, a series is present, a receipt is sealed) must resolve to real evidence, not a string that looks right — extend the "reference resolves" discipline from cluster objects to evidence artifacts. | future |
| L5 | **Local == CI parity.** The commands a developer runs locally must be byte-for-byte the commands CI runs (`pytest` == `python -m pytest`, same make target, same interpreter), so "green on my machine" and "green in CI" cannot diverge. | future |
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
