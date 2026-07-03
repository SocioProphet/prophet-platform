# ADR-036 — Inception Framework: strict-initial-object invariants

**Status:** Accepted (2026-06-29)
**Context decision:** "Adopt the Inception Framework as the formal contract layer now."

## Context

The *Inception Framework* models the platform as a category 𝒞 of typed artifacts and capability-scoped morphisms, with a **strict initial object ∅** (the canonical empty artifact). Three invariants fall out, and we already enforce weaker versions of all three by convention. This ADR upgrades them from convention to **proof**, binding each to a component we already own.

## Decision

Adopt three invariants as platform contracts:

### I1 — Unique genesis (reproducible bootstrap)
There is exactly one canonical genesis morphism `∅ → X`. No ad-hoc bootstrap paths; only the **genesis functor** mints a first instance, and the (digest, signer) of each genesis bundle is recorded in a **genesis registry**.

- **Binds to:** the identity-prime registry genesis (the "Bereshit" first-agent). Genesis bundles (schemas, contexts, policies) are content-addressed and signed; same digest ⇒ same object.
- **Reference:** `tools/strictempty_kit.py::genesis`.

### I2 — No silent discard (certified erasure)
Any morphism `X → ∅` must be a **certified isomorphism**. You cannot route to a bit-bucket; you must transform `X` down to the canonical empty value and prove it: `X --shred--> X₀ --certify--> ∅` where `H(X₀) == H(∅)` under a declared canonicalization.

- **Binds to / upgrades:** the Liberty-Stack **deletion gate** (reversibility-before-destruction). Every delete / redact / quarantine path now emits a **`ProofOfEmptiness`** (`contracts/ProofOfEmptiness.v0.1.json`); the admission path is **fail-closed** — an `X → ∅` flow without a certified PoE is rejected.
- **Reference:** `contracts/ProofOfEmptiness.v0.1.json`, `tools/validate_proof_of_emptiness.py`, `tools/strictempty_kit.py::erase_iso`.

### I3 — Emptiness absorbs (no effect from nothing)
`X × ∅ ≅ ∅`, and execution under the strict-bottom capability `⊥` yields `∅` (`c ⊗ ⊥ = ⊥`). Combining any computation with empty data or zero capability produces no effect — by typing, not by convention.

- **Binds to:** the **autonomy ladder formalized as a capability lattice** (L0–L5 with a strict bottom). A tool running under `⊥` cannot produce a non-empty result; channel-gate sinks compose monoidally.
- **Reference:** `tools/strictempty_kit.py::prod`, `exec_under`.

## Consequences

- **Deletion becomes provable, not asserted** — closes the gap the corpus and Liberty Stack both flagged ("no deletion without restore proof"); now also "no deletion without an emptiness proof."
- **Bootstrap becomes reproducible and attributable** via the genesis registry.
- **The autonomy ladder gains an algebraic floor** (`⊥` absorbs), making "no ambient authority" a type-level property.
- **Enforcement points:** admission webhook / runtime gate rejects uncertified `X → ∅`; CI runs `strictempty_kit.py --selftest` as the property-test oracle; PoE records flow onto the reasoning-evidence fabric like other receipts.

## Non-goals / guardrails

- This is the *operational* algebra. The categorical/topological framing in the Semantic Fibration and Ghost space docs remains **motivating metaphor** — no derived physics numbers (per the cosmic-structure-settled guardrail).
- `ProofOfEmptiness` does not itself perform erasure; it certifies that a sanctioned erase-iso reached ∅.

## References
- `contracts/ProofOfEmptiness.v0.1.json` (+ `.example.json`)
- `tools/validate_proof_of_emptiness.py`, `tools/strictempty_kit.py`
- `adr/ADR-033-canonical-receipts-and-event-envelopes.md`, `contracts/AutonomyAdmissionReceipt.v0.1.json`
- `docs/CANONICAL_COMPONENT_MAP.md`
