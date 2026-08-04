"""Tests for the Crystal Atlas -> market paradigm bridge, both ways.

The bridge translates and nothing else, so most of what is worth testing here is what
it REFUSES: unmapped epistemic levels, cross-tenant joins, and inferred coordinates.
Each is a way a translation layer quietly answers a different question than it was
asked.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from app.market_bridge import (
    BRIDGE_AXES,
    EPISTEMIC_TO_VERDICT,
    BridgeError,
    claims_from_event,
    manifest_from_events,
    market_from_events,
    with_declared_axes,
)

CONTRACTS = pathlib.Path(__file__).resolve().parents[3] / "contracts/crystal-atlas/events"


def _event(**overrides):
    event = {
        "event_id": "evt-1",
        "emitted_at": "2026-08-03T00:00:00Z",
        "tenant_id": "tenant-a",
        "producer": "crystal-atlas-extract-enrich",
        "subject": "acme-corp",
        "epistemic_level": "empirical",
        "provenance": {"source": "doc-1", "method": "extraction", "collected_at": "2026-08-01"},
        "source": {"source_event_type": "doc.clauses.extracted.v0", "source_event_id": "src-1"},
        "value_drivers": [
            {"driver": "retention", "kpi": "churn_rate", "score": 0.8, "equity_weight": 0.5}
        ],
        "overall_value_score": 0.8,
    }
    event.update(overrides)
    return event


# --------------------------------------------------------------------------- #
# The epistemic mapping must be total over the shipped schema
# --------------------------------------------------------------------------- #


def test_the_mapping_covers_every_level_the_schema_allows():
    """A new enum value must fail loudly, not default to something permissive."""
    schema = json.loads((CONTRACTS / "intel.value_driver.scored.v0.schema.json").read_text())
    allowed = set(schema["properties"]["epistemic_level"]["enum"])
    assert allowed == set(EPISTEMIC_TO_VERDICT), (
        "epistemic_level enum and EPISTEMIC_TO_VERDICT have diverged: "
        f"{allowed ^ set(EPISTEMIC_TO_VERDICT)}"
    )


def test_an_unmapped_level_is_refused():
    with pytest.raises(BridgeError) as excinfo:
        claims_from_event(_event(epistemic_level="vibes"))
    assert "deliberately" in str(excinfo.value)


def test_rejected_findings_become_claims_rather_than_vanishing():
    """A rejected finding is still evidence of what was assessed."""
    claims = claims_from_event(_event(epistemic_level="rejected"))
    assert claims[0].verdict == "refuse"


def test_stronger_epistemic_levels_map_to_stronger_verdicts():
    from procyber.semantic.semantic_algebra import VERDICT_ORDER

    proved = VERDICT_ORDER.index(EPISTEMIC_TO_VERDICT["proved"])
    speculative = VERDICT_ORDER.index(EPISTEMIC_TO_VERDICT["speculative"])
    assert proved > speculative


# --------------------------------------------------------------------------- #
# Translation
# --------------------------------------------------------------------------- #


def test_each_value_driver_becomes_its_own_claim():
    """Collapsing drivers would destroy the coordinate the paradigm is keyed on."""
    event = _event(
        value_drivers=[
            {"driver": "retention", "kpi": "churn_rate", "score": 0.8, "equity_weight": 0.5},
            {"driver": "expansion", "kpi": "nrr", "score": 0.6, "equity_weight": 0.5},
        ]
    )
    claims = claims_from_event(event)
    assert len(claims) == 2
    assert {c.cell[0] for c in claims} == {"retention", "expansion"}


def test_the_cell_is_driver_by_subject():
    claim = claims_from_event(_event())[0]
    assert claim.cell == ("retention", "acme-corp")


def test_the_kpi_becomes_the_unit():
    """So two findings scoring the same cell on different KPIs contradict, not average."""
    claim = claims_from_event(_event())[0]
    assert claim.unit == "churn_rate"


def test_different_kpis_on_one_cell_contradict_rather_than_average():
    from procyber.semantic.market_paradigm import reconcile
    from procyber.semantic.semantic_algebra import BOTTOM

    a = claims_from_event(_event(event_id="e1", producer="p1"))[0]
    b = claims_from_event(
        _event(
            event_id="e2",
            producer="p2",
            value_drivers=[
                {"driver": "retention", "kpi": "logo_churn", "score": 0.8, "equity_weight": 0.5}
            ],
        )
    )[0]
    verdict, contradiction = reconcile([a, b])
    assert verdict is BOTTOM
    assert contradiction is not None
    assert "incommensurable" in contradiction.reason


def test_provenance_and_evidence_travel_with_the_claim():
    claim = claims_from_event(_event())[0]
    assert claim.observed_at == "2026-08-01"
    assert claim.evidence_ref == "src-1"


def test_a_missing_required_field_is_refused():
    bad = _event()
    del bad["subject"]
    with pytest.raises(BridgeError):
        claims_from_event(bad)


# --------------------------------------------------------------------------- #
# Tenant scoping — refuse, never filter
# --------------------------------------------------------------------------- #


def test_a_single_tenants_events_build_a_map():
    market = market_from_events([_event()], tenant="tenant-a")
    assert market.ordered_axes() == BRIDGE_AXES
    assert len(market.claims) == 1


def test_a_foreign_tenant_event_is_refused_not_filtered():
    """A silent filter answers a narrower question while looking correct."""
    with pytest.raises(BridgeError) as excinfo:
        market_from_events([_event(), _event(event_id="e2", tenant_id="tenant-b")], tenant="tenant-a")
    assert "refused, not filtered" in str(excinfo.value)


def test_requesting_the_wrong_tenant_refuses_everything():
    with pytest.raises(BridgeError):
        market_from_events([_event()], tenant="tenant-z")


# --------------------------------------------------------------------------- #
# Widening is declared, never inferred
# --------------------------------------------------------------------------- #


def test_widening_records_the_declared_coordinates():
    market = market_from_events([_event()], tenant="tenant-a")
    widened = with_declared_axes(market, geography="emea", modality="cloud")
    assert set(widened.axes) == {"offering", "actor", "geography", "modality"}
    assert widened.axes["geography"] == ("emea",)


def test_widening_preserves_every_claim():
    market = market_from_events([_event()], tenant="tenant-a")
    widened = with_declared_axes(market, geography="emea")
    assert sum(len(v) for v in widened.claims.values()) == sum(
        len(v) for v in market.claims.values()
    )


def test_widening_refuses_to_overwrite_an_existing_axis():
    market = market_from_events([_event()], tenant="tenant-a")
    with pytest.raises(BridgeError):
        with_declared_axes(market, actor="someone-else")


def test_widening_refuses_a_non_paradigm_axis():
    market = market_from_events([_event()], tenant="tenant-a")
    with pytest.raises(BridgeError):
        with_declared_axes(market, astrology="leo")


def test_an_unwidened_map_cannot_merge_with_a_wider_one():
    """The refusal that makes widening necessary — no silent marginalisation."""
    from procyber.semantic.market_paradigm import AxisError, merge

    narrow = market_from_events([_event()], tenant="tenant-a")
    wide = with_declared_axes(
        market_from_events([_event()], tenant="tenant-a"), geography="emea"
    )
    with pytest.raises(AxisError):
        merge(narrow, wide)


# --------------------------------------------------------------------------- #
# Manifest
# --------------------------------------------------------------------------- #


def test_the_manifest_leads_with_gaps_and_coverage():
    event = _event(
        value_drivers=[
            {"driver": "retention", "kpi": "churn_rate", "score": 0.8, "equity_weight": 0.5},
            {"driver": "expansion", "kpi": "nrr", "score": 0.6, "equity_weight": 0.5},
        ]
    )
    manifest = manifest_from_events([event, _event(event_id="e2", subject="globex")], tenant="tenant-a")
    assert manifest["cellsTotal"] > manifest["cellsClaimed"]
    assert manifest["gaps"] > 0
    assert manifest["coverage"] < 1.0


def test_the_manifest_carries_its_tenant_and_source_type():
    manifest = manifest_from_events([_event()], tenant="tenant-a")
    assert manifest["tenantId"] == "tenant-a"
    assert manifest["sourceEventType"] == "intel.value_driver.scored.v0"


def test_the_manifest_reports_the_twin_tiers_this_source_can_feed():
    manifest = manifest_from_events([_event()], tenant="tenant-a")
    assert set(manifest["twinTiers"]) == {"capability", "entity"}
