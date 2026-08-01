# Semantic Coordinate Algebra — provenance register & conformance

Status: v0.1 · stdlib-only kernel in `tools/semantic_algebra.py`

This document is the **provenance register** the module docstring points at. It
doubles as the clean-room warrant: every generating element of the algebra traces
to a public-domain source, so the *system* is unencumbered and owes no attribution
to any third-party formal language. (A formal language and its algebra are a
*system*; systems are not copyrightable — CJEU C-406/10 *SAS v WPL*; 17 U.S.C.
§102(b); *Baker v. Selden*.) The register is the evidence for that claim.

## 1. Generating set — one row per element

| Element | Role in the algebra | Public-domain source | Citation |
|---|---|---|---|
| `NIL` | neutral element; axis marker in a role | algebraic necessity | a monoid needs an identity — not anyone's invention |
| `POT` / `ACT` | the binary symmetry (potentiality / actuality) | Aristotle, *Metaphysics* Θ | δύναμις / ἐνέργεια — matter/form, → `kko:Matter` / `kko:Forms` |
| `FST` / `SND` / `TRD` | the ternary symmetry (Firstness / Secondness / Thirdness) | C. S. Peirce, 1890s | the phenomenological categories — already the KKO spine |
| roles `ground` / `differentia` / `mode` | the three positions of the ternary product | Aristotle (genus + differentia) + Spinoza (mode) | *Categories*; *Ethics* Pt I def. 5 |

Nothing in the generating set is taken from, or requires permission of, any
third-party formal language or metalanguage. Any such comparison lives only in the
internal design register (`SP-DES-*`), **never** in this repo or its public README,
and no element above was derived from a third party's dictionary, definitions, or
grammar prose. (This constraint is enforced, not merely asserted — see
`tools/check_cleanroom.py`.)

## 2. Why an algebra (the measured failure it fixes)

The keyed-vec topic space was flat: an intro-physics query matched a graduate-QFT
topic — 94.9% vocab hit, topic max-cos only 0.38–0.54. Abstraction level was not
*representable*, so it could not be *enforced*. Here `layer` is a **syntactic**
property of an address: a cross-layer match is not discouraged by a threshold, it
is structurally impossible. See `bind_tiered` and its rejection test.

## 3. Conformance (what the tests pin, both ways)

* Terms are immutable, hashable; equality is structural.
* `add` is commutative and normalised — no two formally different expressions
  denote the same set.
* `mul` is **non-commutative** and raises on mixed-layer operands; layer
  discipline is enforced at construction, not checked after the fact.
* `pullback` (limit/restrict) and `pushout` (colimit/glue) are duals and the only
  two ways to combine knowledge; `meet` reconciles them. **One** `meet`
  implementation serves both this kernel and `Truth = Law × Evidence`.
* Every guard is exercised on its refusal path too: a guard only ever seen to
  allow is not evidence of a guard.

## 4. Layering (the abstraction bar)

`MAX_LAYER = 4`. `distance` is undefined across layers and raises; `bind_tiered`
grounds general-first and admits a lower-tier candidate **only** if its `ground`
role is the upper anchor actually landed on. That structural rule — not a tunable
cosine threshold — is the abstraction-level bar, and it is what the S5 gate
(`tools/abstraction_level_gate.py`) measures.

## 5. Attribution posture

Legally owed: none, provided no third-party protected expression is used.
Publicly cited: **Peirce, Spinoza, Aristotle, Tesnière** — the actual provenance.
Marks of third parties are not used to name anything in this system.
