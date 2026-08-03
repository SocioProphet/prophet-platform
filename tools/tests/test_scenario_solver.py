from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import scenario_solver as ss  # type: ignore
from causal_identification import Dag  # type: ignore


def _pf(name, value, lo, hi):
    return ss.ParameterFact(name=name, value=value, interval=(lo, hi), n=30,
                            provenance="test", epistemic_level="empirical", as_of="2026-08-01T00:00:00+00:00")


def _identified_dag():
    # T<-C->Y and T->Y: backdoor via measured confounder C -> identifiable.
    return Dag(nodes={"T", "Y", "C"}, edges=[("C", "T"), ("C", "Y"), ("T", "Y")], measured={"T", "Y", "C"})


def _unidentified_dag():
    # T<-U->Y with U unmeasured: unblockable backdoor -> not identifiable.
    return Dag(nodes={"T", "Y", "U"}, edges=[("U", "T"), ("U", "Y"), ("T", "Y")], measured={"T", "Y"})


def _spec(dag, *, reaction="L0", elast=(0.9, 1.1), seed=0):
    return ss.ScenarioSpec(
        estimand_id="reprice-Y", dag=dag, treatment="T", outcome="Y",
        intervention={"magnitude": -0.08},
        parameters={"elasticity": _pf("elasticity", 1.0, *elast),
                    "competitor_reaction": _pf("competitor_reaction", 0.3, 0.2, 0.4)},
        graph_snapshot_hash="g:abc", parameter_vintage="2026-08-01", reaction_level=reaction, seed=seed,
    )


def test_unidentified_refuses_point_estimate():
    r = ss.solve(_spec(_unidentified_dag()))
    assert r.refused is True
    assert r.distribution is None                     # NO point estimate / distribution
    assert r.identification_status == "not_identified"
    assert r.bounds is not None                       # non-causal bounds instead
    assert r.blocking_structure                       # tells the customer why
    assert r.label == "non_causal_bounds_only"


def test_identified_returns_a_distribution_not_a_scalar():
    r = ss.solve(_spec(_identified_dag()))
    assert r.refused is False
    assert r.distribution is not None
    d = r.distribution
    assert d.p05 <= d.p50 <= d.p95                    # a distribution, never a single number
    assert d.n_samples == 512
    assert "C" in r.adjustment_set                    # identified by adjusting for C


def test_parameter_uncertainty_propagates():
    narrow = ss.solve(_spec(_identified_dag(), elast=(0.99, 1.01))).distribution
    wide = ss.solve(_spec(_identified_dag(), elast=(0.5, 1.5))).distribution
    assert (wide.p95 - wide.p05) > (narrow.p95 - narrow.p05)  # wider input -> wider output


def test_deterministic_replay_is_bit_identical():
    r1 = ss.solve(_spec(_identified_dag(), seed=7))
    r2 = ss.solve(_spec(_identified_dag(), seed=7))
    assert r1.content_address == r2.content_address
    assert r1.distribution == r2.distribution        # replays exactly
    # different seed -> same content address only if seed is part of it (it is) -> differs
    r3 = ss.solve(_spec(_identified_dag(), seed=8))
    assert r3.content_address != r1.content_address


def test_L0_is_labelled_a_bound_and_L1_reacts():
    l0 = ss.solve(_spec(_identified_dag(), reaction="L0"))
    l1 = ss.solve(_spec(_identified_dag(), reaction="L1"))
    assert l0.label == "upper_bound_on_own_move"      # L0 never sold as a forecast
    assert l1.label != "upper_bound_on_own_move"
    # L1 competitor reaction dampens the own-move effect.
    assert abs(l1.distribution.p50) < abs(l0.distribution.p50)


def test_content_address_reacts_to_certifying_inputs():
    base = ss.solve(_spec(_identified_dag())).content_address
    # changing the reaction level changes the certified identity
    assert ss.solve(_spec(_identified_dag(), reaction="L1")).content_address != base


def test_unknown_reaction_level_rejected():
    with pytest.raises(ValueError):
        ss.solve(_spec(_identified_dag(), reaction="L9"))
