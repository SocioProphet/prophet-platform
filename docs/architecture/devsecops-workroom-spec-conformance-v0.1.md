# DevSecOps Workroom — Shared-Spec Conformance Profile v0.1

**Status:** authored 2026-07-31 · validated against the three shared specs below
**Owner:** Platform / DevSecOps
**Binds:** `devsecops-intelligence-workroom-v0.1` + `…-guardrail-action-safety-scope-v0.1`
to the Kappa mesh (`kappa-eventbus-telemetry-slashtopics-v0.1`).

Machine-checkable form: `contracts/workroom/workroom-spec-conformance.v0.1.json`
enforced by `tools/validate_workroom_spec_conformance.py` (declared ⇒ enforced,
per never-fired=suspect).

## Shared specs (validated by full read, not skim)
- **S1 — Secure Sandbox Evidence Acquisition & AI Execution Governance** (docx):
  execution separation; deterministic, integrity-preserving evidence capture
  (timestamped, rsync-metadata, `stat/find` inventory, MIME-gated transcript,
  **SHA-256 → Merkle** manifest); controlled output.
- **S2 — Tree-Sitter Authoring & Three-Space Learning Loops (LSA/LSI/LDA)** (rtf):
  code/logs/configs → **Event-IR** (typed, `ir-validate` fail-closed) → LSA/LSI/LDA
  spaces (pinned seeds/dims, signed manifests) → analyzer **ProofArtifacts**;
  Emergence gate (unitary updates only after coverage/stability).
- **S3 — ScientistOne vs BAAP-Superior** (pdf): native provenance ≫ forensic
  reconstruction; **epistemicLevel 6-state gradient** (proved/bounded/empirical/
  synthetic/speculative/rejected) as a strict superset of CoE's 4 booleans;
  uncertainty is first-class; **manifest-gate for ALL authority incl. static/
  curated sources** (ARC seminal-papers YAML failure).

## Conformance matrix
| # | Requirement (source) | Status | Binding / evidence |
|---|---|---|---|
| C1 | Execution separation — no privileged action without explicit grant + policy eval (S1 §3.1) | ✅ conforms | workroom `requires_human_approval`; "not the execution authority"; AgentPlane owns execution |
| C2 | Evidence-grade capture: deterministic + integrity manifest (SHA-256→Merkle) (S1 §5,§12) | ⚠️ partial | workroom cites "evidence artifacts, receipts" but MUST **require** every evidence bundle carry a hash/Merkle manifest before it can back a claim |
| C3 | Controlled output — MIME-gated, no binary flooding (S1 §3.3,§10.1) | 🆕 bind | applies to workroom evidence ingestion + `/telemetry/logs` producer |
| C4 | Claims flow as **Event-IR**, `ir-validate` fail-closed (S2 §2,§5.2) | 🆕 bind | `evidence_backed_rca_claims` emitted as Event-IR = CDM `EventEnvelope` on `/intel/*` |
| C5 | Claims semantically grounded: attach `(lsa_id, lsi_id, lda_mix)` + ProofArtifact (S2 §3,§5.4) | 🆕 bind | RCA/verdict events carry space coords; analyzer proofs signed to the receipt spine |
| C6 | Emergence gate — unitary space updates only after coverage/stability (S2 §5.5) | 🆕 bind | governs when the intel loop may expand topics (LDA K) / rank (LSI) |
| C7 | Claims carry **epistemicLevel** 6-state + uncertainty, not boolean (S3 §3) | ⚠️ extend | RCA claims/verdicts MUST carry epistemicLevel + calibrated uncertainty to the decision surface |
| C8 | **Native provenance** — evidence captured at claim-production time (S3 §1,§4) | ✅ aligns | workroom is claim-production-time; forbid post-hoc-only provenance |
| C9 | Manifest-gate for ALL authority incl. static/curated sources (S3 §5.1) | 🆕 bind | any allowlist/seed/reference set the workroom or GDI ships MUST register through the membrane gate — no default-trusted exemption |
| C10 | Poisoned evidence cannot become action authority (S1+S3) | ✅ conforms | already a workroom non-negotiable |
| C11 | Convergent evaluator-exploitation test class (S3 §5.3) | 🆕 SCOPE-D | flag to SCOPE-D adversarial suite (benchmark-contract vuln class) |

## Bindings onto the mesh (how the agent actually follows the specs)
- The workroom is the **GDI consumer** closing the loop: consumes `/telemetry/*`
  + `/intel/verdicts`, emits `/ops/findings` + `/ops/actions` — each as an
  Event-IR `EventEnvelope` (C4) carrying `epistemicLevel` + uncertainty (C7),
  space coords + ProofArtifact ref (C5), and an evidence-integrity manifest (C2),
  membrane-gated (C1/C9) with a MembraneDecision receipt → spine.
- Actions (`/ops/actions`) never self-execute (C1); they are grants requiring
  human approval for production change.
- `producer-before-storage` + `feedback-loop-liveness` gates already defined in
  the Kappa ADR extend to enforce C4/C7 presence on every intel event.

## Validation performed
Each shared spec read in full; the workroom v0.1 spec set read and mapped above.
C1/C8/C10 already hold; C2/C7 need tightening; C3/C4/C5/C6/C9 are new bindings
tracked as build items in the Kappa ADR §7 + the conformance profile JSON.

## ScientistOne work-order (S3 §6) disposition
Keep the PDF as a **cited reference** (its own recommendation), not inlined. Its
5 tasks route to: agent-registry manifest-gate (task 3 → C9), SCOPE-D (task 4 →
C11), model-router branch-allocation (task 5, width>depth), and the BAAP-Superior
spec's Prior-Art section (tasks 1–2).
