"""Tests for the market paradigm — the cross-report superset.

Every gate is exercised BOTH ways. The refusal paths matter more than usual
here: this module's whole claim is that it surfaces disagreement and silence
rather than averaging them, and a merge that has only ever been seen to succeed
is not evidence that it refuses anything.
"""

from __future__ import annotations

import json

import pytest

from tools.market_paradigm import (
    AXES,
    TWIN_TIERS,
    VALUE_TOLERANCE,
    AxisError,
    Claim,
    MarketMap,
    cell_address,
    manifest_json,
    merge,
    reconcile,
    stale_claims,
    superset,
    twin_manifest,
    twin_projection,
)
from tools.semantic_algebra import BOTTOM

# --------------------------------------------------------------------------- #
# Fixtures — two small maps over the same axes
# --------------------------------------------------------------------------- #


def _axes(verticals=("bfsi", "telecom"), actors=("vendor:a", "vendor:b")):
    return {
        "offering": ("omnichannel", "analytics"),
        "vertical": verticals,
        "geography": ("na", "emea"),
        "actor": actors,
    }


def _map(source: str, **overrides) -> MarketMap:
    m = MarketMap(axes=_axes(**overrides))
    m.declare(
        Claim(
            cell=("omnichannel", "bfsi", "na", "vendor:a"),
            source=source,
            verdict="probable",
            value=100.0,
            unit="usd_m",
            observed_at="2026-01-01",
        )
    )
    return m


# --------------------------------------------------------------------------- #
# Axis conformance
# --------------------------------------------------------------------------- #


def test_axes_are_ordered_canonically_not_by_declaration():
    m = MarketMap(axes={"actor": ("v",), "offering": ("o",)})
    assert m.ordered_axes() == ("offering", "actor")
    assert m.ordered_axes() == tuple(a for a in AXES if a in m.axes)


def test_unknown_axis_refused():
    with pytest.raises(AxisError):
        MarketMap(axes={"astrology": ("leo",)})


def test_cell_with_wrong_arity_refused():
    m = MarketMap(axes=_axes())
    with pytest.raises(AxisError):
        m.declare(Claim(cell=("omnichannel", "bfsi"), source="s"))


def test_cell_with_undeclared_value_refused():
    m = MarketMap(axes=_axes())
    with pytest.raises(AxisError):
        m.declare(Claim(cell=("omnichannel", "aerospace", "na", "vendor:a"), source="s"))


# --------------------------------------------------------------------------- #
# Coverage and gaps — silence is reported, never interpolated
# --------------------------------------------------------------------------- #


def test_universe_is_the_full_axis_product():
    m = MarketMap(axes=_axes())
    assert len(m.universe()) == 2 * 2 * 2 * 2


def test_gaps_are_every_unclaimed_cell():
    m = _map("report:x")
    assert len(m.claims) == 1
    assert len(m.gaps()) == len(m.universe()) - 1


def test_a_claimed_cell_is_not_a_gap():
    m = _map("report:x")
    assert ("omnichannel", "bfsi", "na", "vendor:a") not in m.gaps()


def test_coverage_is_the_claimed_fraction():
    m = _map("report:x")
    assert m.coverage() == pytest.approx(1 / 16)


def test_empty_map_has_zero_coverage_not_a_crash():
    assert MarketMap(axes=_axes()).coverage() == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# Addressing
# --------------------------------------------------------------------------- #


def test_cell_address_is_structural_and_carries_its_inference_type():
    addr = cell_address(("omnichannel", "bfsi"), ("offering", "vertical"))
    assert addr.inference == "induced"
    assert addr.term is not None


def test_cell_address_refuses_arity_mismatch():
    with pytest.raises(AxisError):
        cell_address(("omnichannel",), ("offering", "vertical"))


# --------------------------------------------------------------------------- #
# Reconciliation
# --------------------------------------------------------------------------- #


def test_no_claims_abstains():
    verdict, contradiction = reconcile([])
    assert verdict is BOTTOM
    assert contradiction is None


def test_agreeing_sources_meet_to_the_weaker_verdict():
    cell = ("omnichannel", "bfsi", "na", "vendor:a")
    verdict, contradiction = reconcile(
        [
            Claim(cell=cell, source="a", verdict="sealed", value=100.0),
            Claim(cell=cell, source="b", verdict="weak", value=104.0),
        ]
    )
    assert contradiction is None
    assert verdict == "weak"


def test_values_within_tolerance_do_not_contradict():
    cell = ("omnichannel", "bfsi", "na", "vendor:a")
    inside = 100.0 * (1 - VALUE_TOLERANCE / 2)
    _, contradiction = reconcile(
        [
            Claim(cell=cell, source="a", value=100.0),
            Claim(cell=cell, source="b", value=inside),
        ]
    )
    assert contradiction is None


def test_values_beyond_tolerance_contradict_and_refuse_a_verdict():
    """The disagreement travels. It must not average into a single number."""
    cell = ("omnichannel", "bfsi", "na", "vendor:a")
    verdict, contradiction = reconcile(
        [
            Claim(cell=cell, source="a", value=100.0),
            Claim(cell=cell, source="b", value=300.0),
        ]
    )
    assert verdict is BOTTOM
    assert contradiction is not None
    assert set(contradiction.sources) == {"a", "b"}
    assert "disagree" in contradiction.reason


def test_incommensurable_units_contradict():
    cell = ("omnichannel", "bfsi", "na", "vendor:a")
    verdict, contradiction = reconcile(
        [
            Claim(cell=cell, source="a", value=100.0, unit="usd_m"),
            Claim(cell=cell, source="b", value=100.0, unit="seats"),
        ]
    )
    assert verdict is BOTTOM
    assert contradiction is not None
    assert "incommensurable" in contradiction.reason


def test_a_claim_without_a_number_is_still_a_claim():
    cell = ("omnichannel", "bfsi", "na", "vendor:a")
    verdict, contradiction = reconcile([Claim(cell=cell, source="a", verdict="probable")])
    assert contradiction is None
    assert verdict == "probable"


# --------------------------------------------------------------------------- #
# Staleness — an elapsed forecast is history, and says so
# --------------------------------------------------------------------------- #


def test_elapsed_horizon_is_stale():
    claim = Claim(cell=("o",), source="s", horizon="2023-12-31")
    assert claim.is_stale("2026-08-01")


def test_unelapsed_horizon_is_not_stale():
    claim = Claim(cell=("o",), source="s", horizon="2030-12-31")
    assert not claim.is_stale("2026-08-01")


def test_claim_without_a_horizon_is_never_stale():
    assert not Claim(cell=("o",), source="s").is_stale("2026-08-01")


def test_stale_claims_are_downgraded_not_dropped():
    """What was believed at the time is still evidence — just no longer current."""
    cell = ("omnichannel", "bfsi", "na", "vendor:a")
    claims = [Claim(cell=cell, source="a", verdict="sealed", horizon="2023-12-31")]
    fresh, _ = reconcile(claims)
    lapsed, _ = reconcile(claims, as_of="2026-08-01")
    assert fresh == "sealed"
    assert lapsed != "sealed"
    assert lapsed is not BOTTOM


def test_stale_claims_are_enumerable():
    m = MarketMap(axes=_axes())
    m.declare(
        Claim(
            cell=("omnichannel", "bfsi", "na", "vendor:a"),
            source="report:2018",
            horizon="2023-12-31",
        )
    )
    assert len(stale_claims(m, "2026-08-01")) == 1
    assert len(stale_claims(m, "2020-01-01")) == 0


# --------------------------------------------------------------------------- #
# Merge and superset
# --------------------------------------------------------------------------- #


def test_merge_unions_axis_values():
    a = _map("report:a")
    b = _map("report:b", verticals=("bfsi", "healthcare"))
    merged, _ = merge(a, b)
    assert set(merged.axes["vertical"]) == {"bfsi", "telecom", "healthcare"}


def test_merge_accumulates_claims_on_a_shared_cell():
    merged, _ = merge(_map("report:a"), _map("report:b"))
    cell = ("omnichannel", "bfsi", "na", "vendor:a")
    assert len(merged.claims[cell]) == 2
    assert {c.source for c in merged.claims[cell]} == {"report:a", "report:b"}


def test_merge_refuses_maps_over_different_axis_sets():
    """Marginalising over a dropped axis is exactly the silent collapse to avoid."""
    a = MarketMap(axes={"offering": ("o",), "actor": ("v",)})
    b = MarketMap(axes={"offering": ("o",)})
    with pytest.raises(AxisError):
        merge(a, b)


def test_merge_surfaces_contradictions_between_sources():
    a = MarketMap(axes=_axes())
    b = MarketMap(axes=_axes())
    cell = ("omnichannel", "bfsi", "na", "vendor:a")
    a.declare(Claim(cell=cell, source="a", value=100.0))
    b.declare(Claim(cell=cell, source="b", value=500.0))
    _, contradictions = merge(a, b)
    assert len(contradictions) == 1
    assert "vendor:a" in contradictions[0].describe()


def test_superset_of_nothing_abstains():
    """No sources and sources-that-found-nothing are different claims."""
    result, contradictions = superset([])
    assert result is BOTTOM
    assert contradictions == ()


def test_superset_of_one_is_that_map():
    m = _map("report:a")
    result, contradictions = superset([m])
    assert result is m
    assert contradictions == ()


def test_superset_accumulates_across_three_maps():
    maps = [
        _map("report:a"),
        _map("report:b", verticals=("bfsi", "healthcare")),
        _map("report:c", verticals=("bfsi", "manufacturing")),
    ]
    result, _ = superset(maps)
    assert set(result.axes["vertical"]) == {
        "bfsi",
        "telecom",
        "healthcare",
        "manufacturing",
    }
    cell = ("omnichannel", "bfsi", "na", "vendor:a")
    assert len(result.claims[cell]) == 3


# --------------------------------------------------------------------------- #
# Twin projection
# --------------------------------------------------------------------------- #


def test_every_declared_tier_projects():
    m = _map("report:a")
    for tier in TWIN_TIERS:
        assert twin_projection(m, tier)


def test_projection_keys_on_the_tier_axis_value():
    m = _map("report:a")
    assert set(twin_projection(m, "industry")) == {"bfsi"}
    assert set(twin_projection(m, "world")) == {"na"}
    assert set(twin_projection(m, "entity")) == {"vendor:a"}
    assert set(twin_projection(m, "capability")) == {"omnichannel"}


def test_projection_retains_every_claim():
    """The projection changes the key, never the evidence."""
    m = _map("report:a")
    m.declare(
        Claim(cell=("analytics", "bfsi", "emea", "vendor:b"), source="report:a", value=5.0)
    )
    projected = twin_projection(m, "industry")
    assert len(projected["bfsi"]) == 2


def test_unknown_tier_refused():
    with pytest.raises(ValueError):
        twin_projection(_map("report:a"), "astral")


def test_tier_without_its_axis_refused():
    m = MarketMap(axes={"offering": ("omnichannel",)})
    with pytest.raises(AxisError):
        twin_projection(m, "entity")


def test_modality_is_not_a_twin_tier():
    """It cuts across every tier rather than owning one."""
    assert "modality" not in TWIN_TIERS.values()


# --------------------------------------------------------------------------- #
# Manifest — leads with what is not known
# --------------------------------------------------------------------------- #


def test_manifest_reports_gaps_and_coverage():
    m = _map("report:a")
    manifest = twin_manifest(m)
    assert manifest["cellsClaimed"] == 1
    assert manifest["gaps"] == manifest["cellsTotal"] - 1
    assert manifest["coverage"] < 0.1


def test_manifest_counts_stale_claims_when_given_an_as_of():
    m = MarketMap(axes=_axes())
    m.declare(
        Claim(
            cell=("omnichannel", "bfsi", "na", "vendor:a"),
            source="report:2018",
            horizon="2023-12-31",
        )
    )
    assert twin_manifest(m, as_of="2026-08-01")["staleClaims"] == 1
    assert twin_manifest(m)["staleClaims"] is None


def test_manifest_lists_contradictions_rather_than_a_count_only():
    m = MarketMap(axes=_axes())
    cell = ("omnichannel", "bfsi", "na", "vendor:a")
    m.declare(Claim(cell=cell, source="a", value=100.0))
    m.declare(Claim(cell=cell, source="b", value=900.0))
    described = twin_manifest(m)["contradictions"]
    assert len(described) == 1
    assert "bfsi" in described[0]


def test_manifest_json_is_canonical_and_parses():
    payload = manifest_json(_map("report:a"))
    assert payload == manifest_json(_map("report:a"))
    assert json.loads(payload)["specVersion"]
