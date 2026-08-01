# Design note — the layer adjunction: `lift ⊣ ground`

Status: DESIGN (code to follow) · Scope: an addition to `tools/semantic_algebra.py`
Motivation: Kant's schematism, made plural and principled. This note is spec + proof
obligations; it deliberately does not ship code, because an adjunction earns its keep
only with a both-ways proof and that deserves its own change.

---

## 1 · The problem

`distance` **raises** across layers, and `bind_tiered` is the single bridge between an
upper and a lower tier. That is safe — it makes the intro-physics → graduate-QFT
mismatch structurally impossible — but it is *only prohibitive*: the algebra can forbid
a cross-abstraction relation, never *express* one. And there is exactly one schema
(tier-anchoring). Kant's schematism is plural: many rules mediate concept and intuition.
We want the same — cross-layer relation that is **possible but only through a named,
warranted morphism**, with room for more than one such morphism.

## 2 · The morphisms

For each layer `n` introduce a pair of maps to/from `n+1`:

- **`lift : L_n → L_{n+1}`** — generalize: place a term one layer up.
- **`ground : L_{n+1} → L_n`** — specialize: recover the layer-`n` term a lifted term
  stands on.

Order the terms of a layer by **refinement**: `a ⊑ b` means "a is at least as specific
as b" (a pins at least the roles b pins, to at least the same specificity). `NIL`-heavy
terms are more general (higher); fully-pinned products are more specific (lower).

## 3 · The recommended construction (makes the proofs cheap)

- `lift(t) = mul(t, NEUTRAL@n, NEUTRAL@n)` — wrap `t` as the `ground` role of an
  otherwise-neutral product one layer up. (`NEUTRAL@n` is `_neutral_at(n)`.)
- `ground(p) = p.roles()["ground"]` for a product `p`; **undefined (⊥) on a leaf**, and
  undefined across the wrong layer.

With this construction the two composites are not merely adjoint, they are a
**section/retraction with a closure**:

1. `ground ∘ lift = id` on `L_n` — lifting then grounding returns the original exactly.
2. `p ⊑ lift(ground(p))` for every product `p` — grounding then lifting *forgets* the
   `differentia` and `mode`, yielding a **generalization** of `p`; `p` refines its own
   re-generalization. This is the closure/coreflection property.

That is a **coreflection** `L_n ↪ L_{n+1}`: `lift` is a full embedding, `ground` its
retraction, and `lift ∘ ground` is idempotent‑up‑to‑refinement (a closure operator on
`L_{n+1}`). The Galois form we require:

> **`ground(y) ⊑ x   ⟺   y ⊑ lift(x)`**   (the adjunction/Galois condition)

## 4 · Proof obligations — the tests that must pass, both ways

A one-directional guard is not a guard, so each law is pinned on its failure path too:

| # | Law | Refusal-path test |
|---|---|---|
| P1 | `lift(t).layer == t.layer + 1`; `ground(lift(t)).layer == t.layer` | lifting a layer-`MAX_LAYER` term **raises** (`LayerError`) |
| P2 | `ground(lift(t)) == t` (section) | `ground` of a **leaf** is ⊥ (BOTTOM), not a guess |
| P3 | `p ⊑ lift(ground(p))` (closure / inflationary in generality) | a term that is **not** a refinement of `lift(ground(p))` fails the ⊑ check |
| P4 | monotonicity: `a ⊑ b ⇒ lift(a) ⊑ lift(b)` and `ground` likewise | a non-monotone counterexample is rejected |
| P5 | Galois: `ground(y) ⊑ x ⟺ y ⊑ lift(x)` | a pair that satisfies one side but not the other **fails** |
| P6 | `distance_bridged(a@n, b@{n+1}) := distance(lift(a), b)` is defined and symmetric to `distance(a, ground(b))` **only through the morphism** | a raw cross-layer `distance(a, b)` still **raises** — the bridge is the *only* legal crossing |

P6 is the point: cross-layer comparison stops being forbidden and becomes *warranted* —
you may compare across a tier, but only by naming the morphism you crossed on, which is
recorded like any other warrant.

## 5 · Why this subsumes `bind_tiered` (and makes schematism plural)

`bind_tiered` becomes a special case: admit a lower candidate `c` under an anchor `A`
iff `c ⊑ ground(A)` — i.e. `c` injects through the grounded anchor. The current
implementation is exactly this with the projection construction of §3.

Plural schematism falls out by allowing **more than one** `(lift, ground)` pair with
different bridging semantics — e.g. a *taxonomic* schema (genus/species, the §3
construction) and a *mereological* schema (part/whole, where `ground` selects a
component role rather than the genus). Each is a named morphism; each carries its own
warrant; the raw `distance` raise remains the default for any crossing not licensed by
a schema. One kernel, several schematisms, no un-typed leaps.

## 6 · API sketch (for the follow-up change)

```python
def lift(t: Term) -> Term: ...                  # raises LayerError at MAX_LAYER
def ground(p: Term) -> "Term | Abstain": ...    # BOTTOM on a leaf
def refines(a: Term, b: Term) -> bool: ...       # the ⊑ relation, same-layer
def distance_bridged(lo: Term, hi: Term) -> int: ...  # the only legal cross-layer compare
```

No change to existing signatures; `bind_tiered` may later be re-expressed in terms of
`ground` + `refines` once P1–P6 are green.

## 7 · Open

- The refinement relation `⊑` must itself be pinned by test (both a positive and a
  non-refinement pair), since P3–P5 all lean on it.
- Whether `distance_bridged` should compose across more than one layer (n → n+2) or be
  restricted to adjacent layers; recommend adjacent-only until a use forces otherwise
  (economy — Mach).
