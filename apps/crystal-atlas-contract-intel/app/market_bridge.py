"""Market bridge — Crystal Atlas value-driver events into the semantic market paradigm.

This is the seam the semantic kernel was built for. `intel.value_driver.scored.v0`
carries a scored finding about an entity; `procyber.semantic.market_paradigm` knows how
to hold many such findings as a paradigm, reconcile them, and report where they
disagree or fall silent. This module is the translation and nothing else — it
reimplements no reconciliation, no merging, and no contradiction logic.

Axis mapping — honest about what this source carries
----------------------------------------------------
    offering  <- value_driver.driver   (what is being valued)
    actor     <- subject               (the entity the finding concerns)

Two of the paradigm's five axes. `modality`, `vertical` and `geography` are simply not
in this event, and inventing them would be worse than omitting them: `merge` requires
matching axis SETS precisely so that a map missing a dimension cannot be silently
marginalised into one that has it. `with_declared_axes` exists for when a caller
genuinely knows the missing coordinates and is prepared to say so on the record.

Why `kpi` becomes the unit
--------------------------
`market_paradigm.reconcile` treats differing units as incommensurable and raises a
contradiction rather than averaging. Two findings that score the same (driver, subject)
cell against *different KPIs* are exactly that — not a disagreement to be averaged, but
two different measurements wearing the same label. Mapping `kpi` onto `unit` gets that
behaviour for free.

Tenant scoping
--------------
The lane's standing rule is that cross-document joins stay tenant-scoped by default.
`market_from_events` therefore takes the tenant explicitly and REFUSES any event that
does not match, rather than partitioning silently. A quiet partition would look
identical to a correct result while answering a different question.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple

from procyber.semantic.market_paradigm import (
    Claim,
    Contradiction,
    MarketMap,
    twin_manifest,
)

SPEC_VERSION = "0.1.0"

SOURCE_EVENT_TYPE = "intel.value_driver.scored.v0"

#: `epistemic_level` -> the kernel's verdict lattice. TOTAL over the schema enum: a new
#: level must be mapped deliberately rather than defaulting to something permissive.
#: `rejected` maps to `refuse` rather than being dropped — a rejected finding is still
#: evidence of what was assessed, and the lattice will cap it wherever it appears.
EPISTEMIC_TO_VERDICT: Dict[str, str] = {
    "proved": "sealed",
    "bounded": "probable",
    "empirical": "probable",
    "synthetic": "weak",
    "speculative": "quarantine",
    "rejected": "refuse",
}

#: The axes this event source can actually populate. See the module docstring.
BRIDGE_AXES: Tuple[str, ...] = ("offering", "actor")


class BridgeError(ValueError):
    """Raised when an event cannot be translated without inventing something."""


def _require(event: Mapping[str, Any], field: str) -> Any:
    if field not in event:
        raise BridgeError(f"{SOURCE_EVENT_TYPE} missing required field {field!r}")
    return event[field]


def claims_from_event(event: Mapping[str, Any]) -> Tuple[Claim, ...]:
    """One `Claim` per value driver on the event.

    A finding scoring five drivers is five claims, not one averaged claim: the
    paradigm's cell is (driver, subject), so collapsing them here would destroy the
    coordinate the whole structure is keyed on.
    """
    subject = _require(event, "subject")
    level = _require(event, "epistemic_level")
    if level not in EPISTEMIC_TO_VERDICT:
        raise BridgeError(
            f"unmapped epistemic_level {level!r}; add it to EPISTEMIC_TO_VERDICT "
            "deliberately rather than defaulting"
        )
    verdict = EPISTEMIC_TO_VERDICT[level]

    provenance = event.get("provenance") or {}
    source = event.get("source") or {}
    observed_at = provenance.get("collected_at")
    # The upstream event id is the evidence pointer; without it a claim has no
    # provenance chain and the withhold side of any later share decision will say so.
    evidence_ref = source.get("source_event_id") or event.get("event_id")

    claims = []
    for driver in _require(event, "value_drivers"):
        claims.append(
            Claim(
                cell=(driver["driver"], subject),
                source=str(event.get("producer") or event.get("event_id")),
                verdict=verdict,
                value=driver.get("score"),
                unit=driver.get("kpi"),
                observed_at=observed_at,
                evidence_ref=evidence_ref,
            )
        )
    return tuple(claims)


def market_from_events(
    events: Sequence[Mapping[str, Any]], *, tenant: str
) -> MarketMap:
    """Build a tenant-scoped market map from value-driver events.

    Refuses events belonging to another tenant instead of filtering them out. A silent
    filter produces a map that looks correct while answering a narrower question than
    the caller asked, which is the failure mode tenant scoping exists to prevent.
    """
    selected = []
    for event in events:
        event_tenant = event.get("tenant_id")
        if event_tenant != tenant:
            raise BridgeError(
                f"event {event.get('event_id')!r} belongs to tenant {event_tenant!r}, "
                f"not {tenant!r} — cross-tenant joins are refused, not filtered"
            )
        selected.append(event)

    all_claims: list[Claim] = []
    for event in selected:
        all_claims.extend(claims_from_event(event))

    offerings = sorted({c.cell[0] for c in all_claims})
    actors = sorted({c.cell[1] for c in all_claims})
    market = MarketMap(axes={"offering": tuple(offerings), "actor": tuple(actors)})
    for claim in all_claims:
        market.declare(claim)
    return market


def with_declared_axes(market: MarketMap, **fills: str) -> MarketMap:
    """Lift a map onto more axes by DECLARING the missing coordinates explicitly.

    This exists so that widening is a recorded decision rather than an implicit one.
    A caller who knows every claim in this map is (say) EMEA and cloud says so here,
    on the record, and the widened map can then merge with sources carrying those
    axes. Nothing infers a coordinate.
    """
    unknown = set(fills) & set(market.axes)
    if unknown:
        raise BridgeError(f"axes already present, refusing to overwrite: {sorted(unknown)}")

    from procyber.semantic.market_paradigm import AXES

    bad = set(fills) - set(AXES)
    if bad:
        raise BridgeError(f"not paradigm axes: {sorted(bad)}")

    axes = {**{k: v for k, v in market.axes.items()}, **{k: (v,) for k, v in fills.items()}}
    widened = MarketMap(axes=axes)
    ordered = widened.ordered_axes()
    old_order = market.ordered_axes()

    for cell, claims in market.claims.items():
        old = dict(zip(old_order, cell))
        new_cell = tuple(old.get(axis, fills.get(axis, "")) for axis in ordered)
        for claim in claims:
            widened.declare(
                Claim(
                    cell=new_cell,
                    source=claim.source,
                    verdict=claim.verdict,
                    value=claim.value,
                    unit=claim.unit,
                    observed_at=claim.observed_at,
                    horizon=claim.horizon,
                    evidence_ref=claim.evidence_ref,
                )
            )
    return widened


def manifest_from_events(
    events: Sequence[Mapping[str, Any]], *, tenant: str, as_of: str | None = None
) -> Dict[str, Any]:
    """The cockpit payload: coverage, gaps, contradictions, per-tier fill.

    Leads with what is not known, because a value surface that shows only the cells it
    has scored reads as authoritative regardless of how little it covers.
    """
    market = market_from_events(events, tenant=tenant)
    manifest = dict(twin_manifest(market, as_of=as_of))
    manifest["bridgeSpecVersion"] = SPEC_VERSION
    manifest["sourceEventType"] = SOURCE_EVENT_TYPE
    manifest["tenantId"] = tenant
    return manifest
