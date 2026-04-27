# SourceOS Image Production SOTA Program Readout

Status: active
Owner: Prophet Platform
Last updated: 2026-04-27

## Purpose

This document is the program-level readout for the SourceOS image-production, M2 lifecycle proof, Foreman/Katello substrate, and governed execution workstreams.

It exists to make progress visible, measurable, and hard to hand-wave. The target is not merely functional. The target is state-of-the-art: deterministic, evidence-forward, auditable, replayable, secure by default, and aligned to the correct source-of-truth boundaries.

## Operating definition of SOTA

For this program, SOTA means:

```text
State-of-the-art = production-grade capability with explicit authority boundaries, reproducible artifacts, strong evidence, governed promotion, rollback, security review, and measurable non-regression.
```

A workstream is not SOTA because it has a document. It becomes SOTA when it has:

1. a canonical owner;
2. machine-readable contracts;
3. runnable or enforceable implementation;
4. evidence artifacts;
5. validation or CI gates;
6. promotion and rollback semantics;
7. Angel of the Lord / adversarial review where required;
8. integration readout with risks and next actions.

## Correct authority map

```text
SociOS-Linux/SourceOS
  owns artifact truth:
    - flavors
    - coreos-assembler / image composition inputs
    - Butane / Ignition source material
    - installer profiles
    - channels
    - manifests

SociOS-Linux/socios
  owns opt-in automation:
    - Foreman / Katello management hosts
    - Smart Proxies
    - Tekton build/customize/sign/publish/promote
    - Argo CD automation services
    - enrollment, rollout, and promotion automation

SourceOS-Linux/sourceos-spec
  owns shared typed contracts:
    - schema families
    - URN discipline
    - metadata / agent-plane contract model
    - shared content/build/release object family

SocioProphet/prophet-platform
  owns product/control-plane integration:
    - ReleaseSet / BootReleaseSet modeling
    - M2 lifecycle proof
    - website/control-plane path
    - component inventory
    - proof bundles

SocioProphet/agentplane
  owns governed execution:
    - Bundle -> Validate -> Place -> Run -> Evidence -> Replay
    - ValidationArtifact
    - PlacementDecision
    - RunArtifact
    - ReplayArtifact

SocioProphet/sociosphere
  owns governance boundaries:
    - canonical source maps
    - Angel of the Lord critique
    - cross-repo boundary enforcement
```

## Workstream scorecard

Scores are directional and evidence-based, not morale-based.

| Workstream | Current score | Evidence | SOTA gap | Next best action |
|---|---:|---|---|---|
| SourceOS artifact truth | 65% | `SociOS-Linux/SourceOS` has artifact-truth boundaries, flavor stub, installer/channel/manifest directories | Need richer schemas and concrete ReleaseManifest/EvidenceBundle alignment | Expand flavor, installer, channel, and manifest examples against `sourceos-spec` |
| socios Foreman/Katello automation | 60% | FCOS+Foreman/Katello substrate doc, Katello content model, Tekton live ISO customize/publish/smoke tasks | Need signing, pinned sources, Smart Proxy automation, Vault/Tang/object-store wiring, real host smoke tests | Add production lane smoke receipt and signed artifact evidence |
| Prophet Platform M2 lifecycle proof | 70% | deterministic M2 proof generator and proof objects for ConfigSource, ReleaseSet, BootReleaseSet, nlboot crosswalk, Fingerprint, ComplianceResult, ProofIndex | Still proof-only for boot picker, nlboot execution, disk write/install, website UI | Connect proof outputs to component inventory and website/control-plane API path |
| Prophet Platform container/image substrate | 70% | container build substrate doc and component inventory now bind to SourceOS + socios authorities | Need inventory validation and concrete SourceOS image-production component entries with evidence refs | Add inventory validator and SOTA gate checks |
| Agentplane image-production execution lane | 60% | PR #56 adds docs and schema fields for `spec.sourceos`, `spec.sociosAutomation`, `spec.outputs` | Branch behind main; no visible lint status; no example bundle yet | Update/merge PR, then add minimal example bundle and validator rules |
| sourceos-spec shared contracts | 55% | two-plane model, governance lifecycle, URN discipline, existing release/provenance families | Need explicit ReleaseSet/BootReleaseSet/ReleaseManifest/EvidenceBundle alignment if missing | Add only additive schema work; do not duplicate repo-specific semantics |
| Sociosphere governance | 65% | substrate boundary supplement identifies canonical repos and ownership lanes | Need SOTA gates and recurring program readout cadence | Add SOTA gate vocabulary and fold into canonical source map after review |
| Evaluation / evidence fabric | 55% | standards exist for evidence, evaluation, monotonicity, Angel grading, Ray/Beam | Need enforcement in validators and CI | Add validation hooks and example records |

## SOTA gates

A workstream is considered SOTA-ready only when all required gates are green.

### Gate 1 — Authority boundary

- Canonical owner identified.
- No duplicate semantics introduced in downstream repos.
- References point to correct upstream authority.

### Gate 2 — Contract completeness

- Machine-readable schema or contract exists where the object is exchanged.
- Optional extensions do not break existing bundles.
- URNs or stable IDs are defined.

### Gate 3 — Build / execution path

- Runnable path exists or deterministic proof path exists.
- Inputs and outputs are declared.
- Secrets are referenced, never inline.

### Gate 4 — Evidence and replay

- Build/run emits evidence artifact.
- Replay or re-run boundary is declared.
- Output digests, OSTree refs, Katello content refs, or closure hashes exist.

### Gate 5 — Promotion and rollback

- Channel or lifecycle environment exists.
- Promotion state is explicit.
- Previous-known-good or rollback ref is preserved.

### Gate 6 — Security and adversarial review

- Angel of the Lord review applies where release, source exposure, or platform boundary risk exists.
- High/blocker findings prevent promotion.
- Runtime bases and host substrates are classified.

### Gate 7 — Non-regression

- Prior accepted behavior remains non-regressed.
- Stochastic components use repeated-run or confidence-bound evidence where relevant.
- Evaluation records are retained.

## Program risks

### Risk 1 — Semantic duplication

Downstream repos may accidentally redefine SourceOS artifact truth, Katello lifecycle, ReleaseSet semantics, or execution evidence. Mitigation: enforce authority map in Sociosphere and reference canonical repos in docs and schemas.

### Risk 2 — Documentation outruns implementation

The program has many good documents. SOTA requires runnable proof, validators, smoke checks, and evidence artifacts. Mitigation: every new doc must name the runnable path or proof path it supports.

### Risk 3 — PR drift and hidden CI gaps

Agentplane PR #56 is mergeable but behind `main`, and CI status was not visible at last check. Mitigation: update branch, make lint visible, then merge.

### Risk 4 — M2 proof mistaken for live boot proof

The deterministic proof is valuable, but it does not yet prove Apple Silicon boot picker entry, nlboot execution, disk writes, or website UI. Mitigation: keep proof claims precise and add live proof tranches separately.

### Risk 5 — Image bloat

Desktop/server/recovery/service/Beam/Ray images can collapse into bloated general images. Mitigation: immutable image family selection and bloat control gates.

## Next action sequence

1. Merge or prepare Agentplane PR #56 after `lint` runs.
2. Add an Agentplane example bundle for SourceOS image production.
3. Add Agentplane validation rules that fail closed for incomplete `spec.sourceos` and `spec.sociosAutomation` when image-production intent is declared.
4. Add Prophet Platform inventory validator for SourceOS image-production entries.
5. Connect M2 proof bundle outputs into inventory/evidence references.
6. Add Sociosphere SOTA gates and schedule recurring program readouts.
7. Add concrete SourceOS flavor/installer/channel/manifest examples aligned to `sourceos-spec`.

## Readout cadence

Every substantial patch should include:

```text
Program objective
Workstream advanced
Files changed
Evidence produced
Current score change
Risks introduced or reduced
Next best action
```

This is the expected readout format going forward.
