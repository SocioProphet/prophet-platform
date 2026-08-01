"""Compositional semantic algebra — the coordinate kernel (S0-S2).

A graded, non-commutative algebra for *addressing meaning by structure*, so that
semantic distance is COMPUTED from form rather than learned from a corpus. It is
the substrate for two things the estate already needs and does not have:

  1. AgentCoordinateVector — the eleven axes every agent declares itself on, so
     that "what kind of work is this" is a typed value instead of a convention.
  2. SemanticAddress       — a concept address carrying BOTH its intension (how
     it decomposes) and its extension (what it refers to: a KKO/KBpedia IRI),
     plus the warrant for believing it.

Why an algebra at all
---------------------
The measured failure this exists to fix: the keyed-vec topic space is flat, so
an intro-physics query matched a graduate QFT topic — 94.9% vocab hit but topic
max-cos only 0.38-0.54. Abstraction level was not representable, so it could not
be enforced. Here `layer` is a SYNTACTIC property of the address: a cross-layer
match is not discouraged by a threshold, it is structurally impossible (see
`bind_tiered` and its rejection test). That is the whole point.

Primitives and their provenance
-------------------------------
The generating set is forced by the mathematics, not chosen for flavour: to
generate a lattice by symmetry you need a neutral element, one binary symmetry,
and one ternary symmetry. We take ours from the public-domain sources this
estate is ALREADY aligned to, which is why the algebra lands natively on KKO:

  NIL         neutral element                       (algebraic necessity)
  POT / ACT   potentiality / actuality              (Aristotle) -> kko:Matter/Forms
  FST/SND/TRD Firstness / Secondness / Thirdness    (Peirce, 1890s) -> KKO spine

The ternary product's three roles are `ground` (what it stands on), `differentia`
(what distinguishes it) and `mode` (how it is qualified) — Aristotelian
genus/differentia plus the Spinozan mode. See docs/SEMANTIC_COORDINATE_ALGEBRA.md
for the full provenance register; every element traces to a public-domain source.

Pure and local-first: stdlib only, no network. An addressing kernel in the hot
path of every retrieval and every boundary crossing must not take a round-trip.

Conformance notes
-----------------
* Terms are immutable and hashable; equality is structural.
* `add` is commutative and normalised (sorted canonical form), so no two
  formally different expressions denote the same set.
* `mul` is NON-commutative and raises on mixed-layer operands — layer discipline
  is enforced at construction, not checked afterwards.
* `pullback` (limit / restrict) and `pushout` (colimit / glue) are duals and are
  the only two ways to combine knowledge. `meet` reconciles them. One meet
  implementation serves both this kernel and Truth = Law x Evidence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, Optional, Sequence, Tuple

SPEC_VERSION = "0.1.0"

MAX_LAYER = 4

# --------------------------------------------------------------------------- #
# 1. Primitives — the generating set (see provenance register in the docs)
# --------------------------------------------------------------------------- #

NIL = "NIL"  # neutral element; also marks an axis of symmetry when in a role
POT = "POT"  # potentiality  — the virtual, the not-yet-actual
ACT = "ACT"  # actuality     — the effective, the concrete
FST = "FST"  # Firstness     — quality, possibility, monadic
SND = "SND"  # Secondness    — fact, reaction, dyadic
TRD = "TRD"  # Thirdness     — law, mediation, triadic

PRIMITIVES: Tuple[str, ...] = (NIL, POT, ACT, FST, SND, TRD)

#: The two irreducible symmetries. Named sets, not new primitives — a paradigm
#: variable in a role ranges over one of these.
DYAD: Tuple[str, ...] = (POT, ACT)
TRIAD: Tuple[str, ...] = (FST, SND, TRD)
PENTAD: Tuple[str, ...] = DYAD + TRIAD

ROLES: Tuple[str, ...] = ("ground", "differentia", "mode")


# --------------------------------------------------------------------------- #
# 2. Terms — the graded algebra
# --------------------------------------------------------------------------- #


class LayerError(ValueError):
    """Raised when an operation would cross or exceed the layer grading.

    Layer discipline is the mechanism that bars the abstraction-level mismatch
    the tiered-ontology work was built to fix. It fails loudly on purpose.
    """


@dataclass(frozen=True)
class Term:
    """A point in the algebra: either a primitive (layer 0) or a product.

    A product holds exactly three sub-terms, one per role, all at layer n-1;
    the product itself is at layer n. `mode` defaults to the neutral element,
    which is how most words are formed.
    """

    primitive: Optional[str] = None
    ground: Optional["Term"] = None
    differentia: Optional["Term"] = None
    mode: Optional["Term"] = None

    def __post_init__(self) -> None:
        is_leaf = self.primitive is not None
        is_product = self.ground is not None
        if is_leaf == is_product:
            raise ValueError("a Term is either a primitive or a product, not both/neither")
        if is_leaf and self.primitive not in PRIMITIVES:
            raise ValueError(f"unknown primitive {self.primitive!r}")

    # -- grading ---------------------------------------------------------- #

    @property
    def layer(self) -> int:
        if self.primitive is not None:
            return 0
        return self.ground.layer + 1  # type: ignore[union-attr]

    @property
    def is_leaf(self) -> bool:
        return self.primitive is not None

    def roles(self) -> Dict[str, "Term"]:
        if self.is_leaf:
            return {}
        return {
            "ground": self.ground,  # type: ignore[dict-item]
            "differentia": self.differentia,  # type: ignore[dict-item]
            "mode": self.mode,  # type: ignore[dict-item]
        }

    # -- canonical form --------------------------------------------------- #

    def code(self) -> str:
        """Canonical string form. Layer is readable off the bracket depth."""
        if self.is_leaf:
            return str(self.primitive)
        return (
            f"({self.ground.code()}"  # type: ignore[union-attr]
            f" {self.differentia.code()}"  # type: ignore[union-attr]
            f" {self.mode.code()})"  # type: ignore[union-attr]
        )

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.code()


def prim(symbol: str) -> Term:
    """Lift a primitive symbol to a layer-0 term."""
    return Term(primitive=symbol)


NIL_TERM = prim(NIL)


def mul(ground: Term, differentia: Term, mode: Optional[Term] = None) -> Term:
    """The ternary, NON-commutative product. Elides `mode` to the neutral element.

    All three operands must sit at the same layer; the product lands one layer
    up. Crossing layers raises rather than coercing — a silent coercion here is
    exactly how an intro-level concept ends up matching a graduate-level one.
    """
    mode_term = mode if mode is not None else _neutral_at(ground.layer)
    operands = (ground, differentia, mode_term)
    layers = {t.layer for t in operands}
    if len(layers) != 1:
        raise LayerError(
            f"mul requires operands at one layer, got {sorted(layers)}"
        )
    layer = layers.pop()
    if layer + 1 > MAX_LAYER:
        raise LayerError(f"product would reach layer {layer + 1}, max is {MAX_LAYER}")
    return Term(ground=ground, differentia=differentia, mode=mode_term)


def _neutral_at(layer: int) -> Term:
    """The neutral element lifted to `layer` — NIL, NIL*NIL, and so on."""
    term = NIL_TERM
    for _ in range(layer):
        term = Term(ground=term, differentia=term, mode=term)
    return term


@dataclass(frozen=True)
class TermSet:
    """A normalised union of same-layer terms — the additive side of the ring.

    This is what a paradigm variable ranges over. Commutative and idempotent;
    the canonical ordering guarantees no two formally different expressions
    denote the same set.
    """

    terms: FrozenSet[Term]

    def __post_init__(self) -> None:
        if not self.terms:
            raise ValueError("a TermSet must be non-empty")
        layers = {t.layer for t in self.terms}
        if len(layers) != 1:
            raise LayerError(f"a TermSet is single-layer, got {sorted(layers)}")

    @property
    def layer(self) -> int:
        return next(iter(self.terms)).layer

    def code(self) -> str:
        return " + ".join(sorted(t.code() for t in self.terms))

    def __iter__(self):
        return iter(sorted(self.terms, key=lambda t: t.code()))

    def __len__(self) -> int:
        return len(self.terms)


def add(*terms: Term) -> TermSet:
    """Commutative, normalised union of same-layer terms."""
    return TermSet(frozenset(terms))


def distribute(
    ground: "Term | TermSet",
    differentia: "Term | TermSet",
    mode: "Term | TermSet | None" = None,
) -> TermSet:
    """Multiplication distributed over addition — this is how a paradigm is generated.

    A root paradigm is exactly this call with one to three roles filled by a
    TermSet (the variable roles) and the rest by a Term (the invariants). The
    result is the paradigm's cells.
    """

    def _as_set(x: "Term | TermSet | None", layer_hint: int) -> TermSet:
        if x is None:
            return TermSet(frozenset({_neutral_at(layer_hint)}))
        if isinstance(x, TermSet):
            return x
        return TermSet(frozenset({x}))

    g_layer = ground.layer
    g, d = _as_set(ground, g_layer), _as_set(differentia, g_layer)
    m = _as_set(mode, g_layer)
    cells = {mul(gi, di, mi) for gi in g for di in d for mi in m}
    return TermSet(frozenset(cells))


# --------------------------------------------------------------------------- #
# 3. Distance — semantic distance IS structural distance
# --------------------------------------------------------------------------- #


def distance(a: Term, b: Term) -> int:
    """Structural edit distance between two terms at the same layer.

    Zero iff identical. Terms differing in one role are at distance 1, which is
    what makes a paradigm row/column a genuine neighbourhood: nothing is learned
    and nothing is curated per pair.

    Raises on cross-layer comparison — see `bind_tiered` for why.
    """
    if a.layer != b.layer:
        raise LayerError(
            f"distance is undefined across layers ({a.layer} vs {b.layer}); "
            "compare within a layer or ground through the tier bridge"
        )
    if a == b:
        return 0
    if a.is_leaf or b.is_leaf:
        return 1
    return sum(
        distance(a.roles()[r], b.roles()[r]) > 0 and 1 or 0 for r in ROLES
    ) or 1


def neighbours(target: Term, candidates: Iterable[Term], radius: int = 1) -> Tuple[Term, ...]:
    """Candidates within `radius` of `target`, nearest first. Cross-layer skipped."""
    scored = []
    for c in candidates:
        if c.layer != target.layer:
            continue
        d = distance(target, c)
        if d <= radius:
            scored.append((d, c.code(), c))
    return tuple(c for _, _, c in sorted(scored))


# --------------------------------------------------------------------------- #
# 4. The two dual operators, and the meet that reconciles them
# --------------------------------------------------------------------------- #


def pullback(candidates: TermSet, constraint: Dict[str, Term]) -> Optional[TermSet]:
    """LIMIT / restrict — keep only the cells agreeing with `constraint` on each role.

    The restrictive operator. Returns None when the restriction is total, which
    callers must treat as a refusal rather than as an empty-but-fine result.
    """
    kept = set()
    for cell in candidates.terms:
        if cell.is_leaf:
            continue
        if all(cell.roles()[role] == want for role, want in constraint.items()):
            kept.add(cell)
    return TermSet(frozenset(kept)) if kept else None


def pushout(a: Term, b: Term, along: str) -> Term:
    """COLIMIT / glue — combine two terms that agree on the shared role `along`.

    The expansive operator. Refuses to glue along a role where the two disagree:
    gluing over a disagreement is how contradictory knowledge silently merges.
    """
    if along not in ROLES:
        raise ValueError(f"unknown role {along!r}")
    if a.is_leaf or b.is_leaf:
        raise ValueError("pushout requires products, not primitives")
    if a.layer != b.layer:
        raise LayerError(f"pushout across layers ({a.layer} vs {b.layer})")
    if a.roles()[along] != b.roles()[along]:
        raise ValueError(
            f"cannot glue along {along!r}: {a.roles()[along].code()} "
            f"!= {b.roles()[along].code()}"
        )
    merged = {}
    for role in ROLES:
        av, bv = a.roles()[role], b.roles()[role]
        merged[role] = av if av == bv else _neutral_at(av.layer)
    return mul(merged["ground"], merged["differentia"], merged["mode"])


#: The verdict lattice, weakest to strongest. `meet` takes the minimum, which is
#: the same operation Truth = Law x Evidence uses. One implementation, two call
#: sites — a second copy of this ordering is how the two drift apart.
VERDICT_ORDER: Tuple[str, ...] = ("refuse", "quarantine", "weak", "probable", "sealed")


def meet(*verdicts: str) -> str:
    """Reconcile verdicts by taking the lattice minimum.

    The middle-column operation: an expansive signal never carries a decision on
    its own, because the meet with a restrictive signal cannot exceed it.
    """
    if not verdicts:
        raise ValueError("meet requires at least one verdict")
    unknown = [v for v in verdicts if v not in VERDICT_ORDER]
    if unknown:
        raise ValueError(f"unknown verdict(s): {unknown}")
    return min(verdicts, key=VERDICT_ORDER.index)


# --------------------------------------------------------------------------- #
# 5. Tiered binding — the abstraction-level bar, structural not thresholded
# --------------------------------------------------------------------------- #


def bind_tiered(query: Term, upper: TermSet, lower: TermSet) -> Optional[Term]:
    """Ground a query general-first: anchor in `upper`, then descend to `lower`.

    A lower-tier candidate is admitted ONLY if it is a product whose `ground`
    role is the upper anchor we actually landed on. That is what bars an
    intro-level query from matching a graduate-level topic: the bar is a
    structural property of the address, not a cosine threshold that can be
    tuned until it stops complaining.

    Returns None when nothing injects through the anchor — an honest abstain.
    """
    if query.layer != upper.layer:
        raise LayerError(
            f"query is at layer {query.layer}, upper tier at {upper.layer}"
        )
    anchors = neighbours(query, upper.terms, radius=1)
    if not anchors:
        return None
    anchor = anchors[0]
    admitted = [
        cell
        for cell in lower.terms
        if not cell.is_leaf and cell.roles()["ground"] == anchor
    ]
    if not admitted:
        return None
    return sorted(admitted, key=lambda t: t.code())[0]


# --------------------------------------------------------------------------- #
# 6. SemanticAddress — intension + extension + warrant
# --------------------------------------------------------------------------- #

INFERENCE_TYPES: Tuple[str, ...] = ("induced", "deduced", "abduced", "asserted")
MOODS: Tuple[str, ...] = ("assert", "quote", "negate", "ask")


@dataclass(frozen=True)
class SemanticAddress:
    """A concept address that carries how it composes, what it refers to, and why.

    `term` is the intension — the algebraic decomposition, from which distance
    to any other address is computed. `iri` is the extension — a KKO/KBpedia
    reference concept, itself resolvable to a Wikidata entity. Neither face is
    sufficient alone: structure without reference cannot be grounded, reference
    without structure cannot be reasoned about compositionally.

    The remaining fields are the warrant. An address whose validity has lapsed
    or whose evidence has been revoked is still a well-formed address; it is the
    warrant, not the addressing, that goes stale.
    """

    term: Term
    iri: Optional[str] = None
    inference: str = "asserted"
    mood: str = "assert"
    confidence: Optional[float] = None
    evidence_ref: Optional[str] = None
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    revocation_ref: Optional[str] = None
    lexicon: Optional[str] = None

    def __post_init__(self) -> None:
        if self.inference not in INFERENCE_TYPES:
            raise ValueError(f"unknown inference type {self.inference!r}")
        if self.mood not in MOODS:
            raise ValueError(f"unknown mood {self.mood!r}")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")

    @property
    def layer(self) -> int:
        return self.term.layer

    @property
    def is_grounded(self) -> bool:
        """True when the address has an extensional anchor, not only structure."""
        return bool(self.iri)

    def skeleton(self) -> Dict[str, object]:
        """The address stripped of everything that could identify its subject.

        Structure travels; surface does not. This is the mechanism behind the
        withhold-on-linkability rule: a counterparty can compute distance
        against our skeleton without ever receiving the descriptor or the
        evidence pointer.
        """
        return {
            "code": self.term.code(),
            "layer": self.layer,
            "inference": self.inference,
            "mood": self.mood,
        }

    def to_json(self) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "specVersion": SPEC_VERSION,
            "code": self.term.code(),
            "layer": self.layer,
            "inference": self.inference,
            "mood": self.mood,
        }
        for key, value in (
            ("iri", self.iri),
            ("confidence", self.confidence),
            ("evidenceRef", self.evidence_ref),
            ("validFrom", self.valid_from),
            ("validUntil", self.valid_until),
            ("revocationRef", self.revocation_ref),
            ("lexicon", self.lexicon),
        ):
            if value is not None:
                payload[key] = value
        return payload


def address_distance(a: SemanticAddress, b: SemanticAddress) -> int:
    """Distance between addresses — structural, and only within a layer."""
    return distance(a.term, b.term)


# --------------------------------------------------------------------------- #
# 7. Lexicons — a parameter, never a canon
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Lexicon:
    """A named, versioned binding of terms to labels.

    Many lexicons bind to one algebra. This is deliberate: a single canonical
    word list is a coverage ceiling (one domain, one language, one author) and a
    licensing chokepoint. Domains that need their own vocabulary bring their own
    lexicon and still share every structural operation.
    """

    name: str
    version: str
    labels: Dict[str, str] = field(default_factory=dict)
    license: str = "unspecified"

    def label(self, term: Term) -> Optional[str]:
        return self.labels.get(term.code())

    def covers(self, term: Term) -> bool:
        return term.code() in self.labels


class LexiconRegistry:
    """Resolution across lexicons, in declared priority order."""

    def __init__(self, lexicons: Sequence[Lexicon] = ()) -> None:
        self._lexicons: list[Lexicon] = list(lexicons)

    def register(self, lexicon: Lexicon) -> None:
        self._lexicons.append(lexicon)

    def resolve(self, term: Term) -> Optional[Tuple[str, Lexicon]]:
        for lex in self._lexicons:
            label = lex.label(term)
            if label is not None:
                return label, lex
        return None

    def coverage(self, terms: Iterable[Term]) -> float:
        terms = list(terms)
        if not terms:
            return 0.0
        hit = sum(1 for t in terms if self.resolve(t) is not None)
        return hit / len(terms)


def canonical_json(payload: object) -> str:
    """JCS-style canonical form, matching the rest of the contracts tooling."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
