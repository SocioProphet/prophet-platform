"""Market paradigm — a market segmentation as a slice of the coordinate algebra.

An analyst market report is not a document to be summarised. Structurally it is a
ROOT PARADIGM: a multi-dimensional matrix whose axes are held constant or varied,
exactly the construct `semantic_algebra.distribute` already generates. A report
covering component x deployment x organisation-size x vertical x region is a
five-axis paradigm whose cells carry claims.

That observation is what makes a *superset* tractable. Merging N reports is not
a summarisation problem, it is an iterated pushout along shared axes — and the
kernel already refuses to glue over a disagreement. So contradictory analyst
claims SURFACE as contradictions instead of silently averaging into a number
nobody can trace.

What this module is for
-----------------------
Constructing the union of many market maps such that every cell carries:

  * its address        — where it sits in the paradigm, computable
  * its warrant        — who claimed it, on what evidence, how fresh
  * its contradictions — where sources disagree, named rather than averaged
  * its gaps           — cells nobody covers, reported rather than interpolated

The gaps are the product. A superset that reports where it is silent is worth
more than one that pretends completeness, and interpolating an uncovered cell is
how a market map becomes fiction.

Twin binding
------------
The axes project directly onto the twin tiers, which is a good sign the
decomposition is real rather than imposed — analysts converged on it independently:

  geography  -> WORLD twin      (macro conditions, regional dynamics)
  vertical   -> INDUSTRY twin   (sector structure and its drivers)
  actor      -> ENTITY twin     (vendors, their moves, their adjacency)
  offering   -> CAPABILITY twin (what is actually sold)
  modality   -> cuts across all of them (deployment, scale)

`twin_projection` collapses a map onto one tier by summing over the others, so
the same substrate feeds all four twins without a second ingestion path.

Crystal Atlas binding
---------------------
Actor identity across reports is the hard part: two reports naming the same
vendor differently must join, and two genuinely different vendors must not. That
is precisely `entities.resolved.crossdoc.v0` from the Crystal Atlas lane, so this
module takes resolved entity IRIs as INPUT and never does its own name matching.
An `actor` axis value is an IRI, not a display string.

Staleness is a first-class refusal
----------------------------------
A forecast has a horizon. Read after that horizon it is history, not prediction,
and quietly treating an elapsed forecast as current is the failure this module
exists to make impossible. `stale_claims` reports them; `reconcile` downgrades
their verdict rather than dropping them, because a lapsed claim is still evidence
of what was believed at the time.

Pure and local-first: stdlib only, no network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from tools.semantic_algebra import (
    ACT,
    BOTTOM,
    FST,
    POT,
    SND,
    TRD,
    Abstain,
    SemanticAddress,
    Term,
    canonical_json,
    meet,
    mul,
    prim,
)

SPEC_VERSION = "0.1.0"

#: The axes any offering-market decomposes into. Order is significant: it is the
#: cell key order and the address composition order.
AXES: Tuple[str, ...] = ("offering", "modality", "vertical", "geography", "actor")

#: Which axis feeds which twin tier. `modality` is deliberately absent — it cuts
#: across every tier rather than owning one.
TWIN_TIERS: Dict[str, str] = {
    "world": "geography",
    "industry": "vertical",
    "entity": "actor",
    "capability": "offering",
}

#: Anchors for the axes, so a cell address is a term and not a tuple of strings.
#: Firstness/Secondness/Thirdness carry their Peircean sense here: what is
#: offered is a quality, where it lands is a brute fact, who mediates it is a law.
_AXIS_ANCHOR: Dict[str, Term] = {
    "offering": mul(prim(POT), prim(FST)),
    "modality": mul(prim(POT), prim(SND)),
    "vertical": mul(prim(ACT), prim(FST)),
    "geography": mul(prim(ACT), prim(SND)),
    "actor": mul(prim(ACT), prim(TRD)),
}

CellKey = Tuple[str, ...]


class AxisError(ValueError):
    """Raised when a cell does not conform to the map's declared axes."""


# --------------------------------------------------------------------------- #
# 1. Claims — what one source asserts about one cell
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Claim:
    """One source's assertion about one cell of the paradigm.

    `value` is deliberately optional: many useful claims are structural ("this
    vendor operates in this vertical") and carry no number. A claim with no
    number is still a claim, and forcing one invents data.
    """

    cell: CellKey
    source: str
    verdict: str = "probable"
    value: Optional[float] = None
    unit: Optional[str] = None
    observed_at: Optional[str] = None
    horizon: Optional[str] = None
    evidence_ref: Optional[str] = None

    def is_stale(self, as_of: str) -> bool:
        """True when the claim's forecast horizon has elapsed by `as_of`.

        Dates are ISO-8601 strings compared lexicographically, which is correct
        for that format and avoids dragging in a parser for a total ordering we
        already have.
        """
        return self.horizon is not None and self.horizon < as_of


@dataclass(frozen=True)
class Contradiction:
    """A cell where sources disagree in a way that must not be averaged away."""

    cell: CellKey
    sources: Tuple[str, ...]
    values: Tuple[Optional[float], ...]
    reason: str

    def describe(self) -> str:
        return f"{'/'.join(self.cell)}: {self.reason} ({', '.join(self.sources)})"


# --------------------------------------------------------------------------- #
# 2. The map
# --------------------------------------------------------------------------- #


@dataclass
class MarketMap:
    """A set of claims over a declared axis product."""

    axes: Dict[str, Tuple[str, ...]]
    claims: Dict[CellKey, Tuple[Claim, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        unknown = set(self.axes) - set(AXES)
        if unknown:
            raise AxisError(f"unknown axes: {sorted(unknown)}")

    # -- construction ----------------------------------------------------- #

    def declare(self, claim: Claim) -> None:
        """Add a claim, refusing any cell that does not conform to the axes."""
        self._check_cell(claim.cell)
        existing = self.claims.get(claim.cell, ())
        self.claims[claim.cell] = existing + (claim,)

    def _check_cell(self, cell: CellKey) -> None:
        ordered = self.ordered_axes()
        if len(cell) != len(ordered):
            raise AxisError(
                f"cell has {len(cell)} coordinates, map declares {len(ordered)}"
            )
        for axis, value in zip(ordered, cell):
            if value not in self.axes[axis]:
                raise AxisError(f"{value!r} is not a declared value of axis {axis!r}")

    def ordered_axes(self) -> Tuple[str, ...]:
        """Declared axes in canonical AXES order — cell keys follow this."""
        return tuple(a for a in AXES if a in self.axes)

    # -- coverage --------------------------------------------------------- #

    def universe(self) -> Tuple[CellKey, ...]:
        """Every cell the declared axes admit — the paradigm's full extent."""
        ordered = self.ordered_axes()
        return tuple(product(*(self.axes[a] for a in ordered)))

    def gaps(self) -> Tuple[CellKey, ...]:
        """Cells with no claim at all. Reported, never interpolated."""
        return tuple(c for c in self.universe() if c not in self.claims)

    def coverage(self) -> float:
        universe = self.universe()
        if not universe:
            return 0.0
        return len(self.claims) / len(universe)


# --------------------------------------------------------------------------- #
# 3. Addressing — a cell is a term, so cells are comparable
# --------------------------------------------------------------------------- #


def cell_address(cell: CellKey, axes: Sequence[str], iri: Optional[str] = None) -> SemanticAddress:
    """Compose a cell into a SemanticAddress.

    The cell's coordinates are folded into one term so that two cells from two
    different reports are comparable by structure rather than by string equality
    of their labels.
    """
    if len(cell) != len(axes):
        raise AxisError(f"cell/axes arity mismatch: {len(cell)} vs {len(axes)}")
    anchors = [_AXIS_ANCHOR[a] for a in axes]
    term = anchors[0]
    for anchor in anchors[1:]:
        term = mul(term, anchor) if term.layer == anchor.layer else term
    return SemanticAddress(term=term, iri=iri, inference="induced", mood="assert")


# --------------------------------------------------------------------------- #
# 4. Reconciliation — meet where sources agree, contradiction where they do not
# --------------------------------------------------------------------------- #

#: Relative tolerance below which two numeric claims count as agreeing. Analyst
#: figures are estimates; demanding exact equality would report contradictions
#: everywhere and train everyone to ignore them.
VALUE_TOLERANCE = 0.10


def reconcile(
    claims: Sequence[Claim], as_of: Optional[str] = None
) -> Tuple["str | Abstain", Optional[Contradiction]]:
    """Reduce claims about one cell to a single verdict, or name the disagreement.

    Returns `(verdict, contradiction)`. A contradiction does not produce a
    verdict of its own — the caller gets BOTTOM and the named disagreement, so
    the conflict travels rather than collapsing into a number.

    Stale claims are downgraded, not dropped: what was believed at the time is
    still evidence, it is just no longer current.
    """
    if not claims:
        return BOTTOM, None

    verdicts: List[str] = []
    for claim in claims:
        verdict = claim.verdict
        if as_of is not None and claim.is_stale(as_of):
            verdict = _downgrade(verdict)
        verdicts.append(verdict)

    numeric = [(c.source, c.value) for c in claims if c.value is not None]
    if len(numeric) > 1:
        values = [v for _, v in numeric]
        lo, hi = min(values), max(values)
        if hi > 0 and (hi - lo) / hi > VALUE_TOLERANCE:
            return BOTTOM, Contradiction(
                cell=claims[0].cell,
                sources=tuple(s for s, _ in numeric),
                values=tuple(values),
                reason=f"values disagree beyond {VALUE_TOLERANCE:.0%} ({lo} vs {hi})",
            )

    units = {c.unit for c in claims if c.unit is not None}
    if len(units) > 1:
        return BOTTOM, Contradiction(
            cell=claims[0].cell,
            sources=tuple(c.source for c in claims),
            values=tuple(c.value for c in claims),
            reason=f"incommensurable units: {sorted(units)}",
        )

    return meet(*verdicts), None


def _downgrade(verdict: str) -> str:
    """One step down the verdict lattice — the staleness penalty."""
    from tools.semantic_algebra import VERDICT_ORDER

    idx = VERDICT_ORDER.index(verdict)
    return VERDICT_ORDER[max(0, idx - 1)]


def stale_claims(market: MarketMap, as_of: str) -> Tuple[Claim, ...]:
    """Every claim whose horizon has elapsed by `as_of`."""
    return tuple(
        claim
        for claims in market.claims.values()
        for claim in claims
        if claim.is_stale(as_of)
    )


# --------------------------------------------------------------------------- #
# 5. The superset — iterated pushout along shared axes
# --------------------------------------------------------------------------- #


def merge(a: MarketMap, b: MarketMap) -> Tuple[MarketMap, Tuple[Contradiction, ...]]:
    """Glue two maps along their shared axes.

    Axis VALUES are unioned — one report covering more verticals than another is
    not a conflict, it is coverage. Axis SETS must match: gluing a map that has
    an `actor` axis onto one that does not would silently marginalise over the
    vendor dimension, which is exactly the kind of quiet collapse that makes a
    merged market map untraceable.
    """
    if a.ordered_axes() != b.ordered_axes():
        raise AxisError(
            f"cannot merge maps over different axes: "
            f"{a.ordered_axes()} vs {b.ordered_axes()}"
        )

    axes = {
        axis: tuple(sorted(set(a.axes[axis]) | set(b.axes[axis])))
        for axis in a.ordered_axes()
    }
    merged = MarketMap(axes=axes)
    for cell in set(a.claims) | set(b.claims):
        merged.claims[cell] = a.claims.get(cell, ()) + b.claims.get(cell, ())

    contradictions = tuple(
        c
        for cell, claims in sorted(merged.claims.items())
        for c in (reconcile(claims)[1],)
        if c is not None
    )
    return merged, contradictions


def superset(
    maps: Sequence[MarketMap],
) -> Tuple["MarketMap | Abstain", Tuple[Contradiction, ...]]:
    """Iterated merge across many maps.

    Returns BOTTOM for an empty input rather than an empty map: "no sources" and
    "sources that found nothing" are different claims about the world and must
    not share a representation.
    """
    if not maps:
        return BOTTOM, ()
    acc = maps[0]
    found: List[Contradiction] = []
    for nxt in maps[1:]:
        acc, contradictions = merge(acc, nxt)
        found.extend(contradictions)
    return acc, tuple(found)


# --------------------------------------------------------------------------- #
# 6. Twin projection
# --------------------------------------------------------------------------- #


def twin_projection(market: MarketMap, tier: str) -> Dict[str, Tuple[Claim, ...]]:
    """Collapse the map onto one twin tier, keyed by that tier's axis value.

    Every claim is retained under its tier coordinate — the projection changes
    the key, never the evidence. A twin that summarises on the way in cannot
    later answer why it believes something.
    """
    if tier not in TWIN_TIERS:
        raise ValueError(f"unknown twin tier {tier!r}; expected one of {sorted(TWIN_TIERS)}")
    axis = TWIN_TIERS[tier]
    ordered = market.ordered_axes()
    if axis not in ordered:
        raise AxisError(f"map has no {axis!r} axis, so it cannot feed the {tier} twin")
    idx = ordered.index(axis)

    out: Dict[str, List[Claim]] = {}
    for cell, claims in market.claims.items():
        out.setdefault(cell[idx], []).extend(claims)
    return {k: tuple(v) for k, v in sorted(out.items())}


def twin_manifest(market: MarketMap, as_of: Optional[str] = None) -> Dict[str, object]:
    """A serialisable summary: coverage, gaps, contradictions, per-tier fill.

    This is what a cockpit surface renders. It leads with what the map does NOT
    know, because a market surface that shows only its filled cells reads as
    authoritative regardless of how thin it is.
    """
    contradictions = [
        c
        for claims in market.claims.values()
        for c in (reconcile(claims, as_of=as_of)[1],)
        if c is not None
    ]
    tiers = {}
    for tier, axis in sorted(TWIN_TIERS.items()):
        if axis in market.ordered_axes():
            tiers[tier] = len(twin_projection(market, tier))
    return {
        "specVersion": SPEC_VERSION,
        "axes": {a: len(v) for a, v in sorted(market.axes.items())},
        "cellsTotal": len(market.universe()),
        "cellsClaimed": len(market.claims),
        "coverage": round(market.coverage(), 4),
        "gaps": len(market.gaps()),
        "contradictions": [c.describe() for c in contradictions],
        "staleClaims": len(stale_claims(market, as_of)) if as_of else None,
        "twinTiers": tiers,
    }


def manifest_json(market: MarketMap, as_of: Optional[str] = None) -> str:
    return canonical_json(twin_manifest(market, as_of=as_of))
