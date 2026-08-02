"""Tests for the Wave-1 causal identification engine (Ecosystem Simulation Substrate).

Layer A decides *may we claim this*, never the value. These tests pin the three
identification outcomes, the fail-closed gate, and the correctness of the
d-separation / backdoor spine on hand-checkable graphs.
"""
from __future__ import annotations

import pytest

from tools.causal_identification import (
    IDENTIFIED,
    IDENTIFIED_UNDER_ASSUMPTION,
    NOT_IDENTIFIED,
    Dag,
    UnidentifiedEstimand,
    d_separated,
    gate,
    identify,
)


def _dag(nodes, edges, measured):
    return Dag(set(nodes), list(edges), set(measured))


# ── identification outcomes ─────────────────────────────────────────────────
def test_measured_confounder_is_identified_with_backdoor_set():
    # Z confounds T and Y, Z observed → adjust for {Z}.
    dag = _dag(["T", "Y", "Z"], [("Z", "T"), ("Z", "Y"), ("T", "Y")], ["T", "Y", "Z"])
    r = identify(dag, "T", "Y", "gyg_price_effect")
    assert r.status == IDENTIFIED
    assert r.adjustment_set == ["Z"]
    assert r.clearable


def test_no_confounding_is_identified_with_empty_set():
    # T → Y only; nothing to adjust for.
    dag = _dag(["T", "Y"], [("T", "Y")], ["T", "Y"])
    r = identify(dag, "T", "Y")
    assert r.status == IDENTIFIED
    assert r.adjustment_set == []


def test_unmeasured_confounder_is_not_identified_and_names_the_measurement():
    # U confounds but is unobserved → REFUSE, and say what to measure.
    dag = _dag(["T", "Y", "U"], [("U", "T"), ("U", "Y"), ("T", "Y")], ["T", "Y"])
    r = identify(dag, "T", "Y")
    assert r.status == NOT_IDENTIFIED
    assert r.measurement_to_identify == ["U"]
    assert not r.clearable
    assert r.blocking_structure  # the blocking backdoor is reported


def test_unmeasured_confounder_identified_only_under_named_assumption():
    # The same graph, but the caller explicitly assumes no confounding via U.
    dag = _dag(["T", "Y", "U"], [("U", "T"), ("U", "Y"), ("T", "Y")], ["T", "Y"])
    r = identify(dag, "T", "Y", assume_unconfounded={"U"})
    assert r.status == IDENTIFIED_UNDER_ASSUMPTION
    assert r.assumptions == ["no_confounding_via:U"]
    assert r.clearable  # a solver may run, but the assumption is on the record


def test_mediator_is_a_descendant_and_never_enters_the_adjustment_set():
    # T → M → Y with an observed confounder Z on T and Y. Adjusting for the
    # mediator M would block the very effect we want; the spine excludes it.
    dag = _dag(
        ["T", "M", "Y", "Z"],
        [("T", "M"), ("M", "Y"), ("Z", "T"), ("Z", "Y")],
        ["T", "M", "Y", "Z"],
    )
    r = identify(dag, "T", "Y")
    assert r.status == IDENTIFIED
    assert "M" not in r.adjustment_set
    assert r.adjustment_set == ["Z"]


def test_adjustment_set_is_minimal():
    # An irrelevant observed variable W (no backdoor role) must be dropped.
    dag = _dag(
        ["T", "Y", "Z", "W"],
        [("Z", "T"), ("Z", "Y"), ("T", "Y"), ("W", "Y")],
        ["T", "Y", "Z", "W"],
    )
    r = identify(dag, "T", "Y")
    assert r.status == IDENTIFIED
    assert r.adjustment_set == ["Z"]  # W excluded — not needed to block a backdoor


# ── the fail-closed gate ────────────────────────────────────────────────────
def test_gate_runs_solver_when_identified():
    dag = _dag(["T", "Y", "Z"], [("Z", "T"), ("Z", "Y"), ("T", "Y")], ["T", "Y", "Z"])
    r = identify(dag, "T", "Y")
    assert gate(r, lambda: 42) == 42


def test_gate_refuses_solver_when_not_identified():
    dag = _dag(["T", "Y", "U"], [("U", "T"), ("U", "Y"), ("T", "Y")], ["T", "Y"])
    r = identify(dag, "T", "Y")
    called = []
    with pytest.raises(UnidentifiedEstimand):
        gate(r, lambda: called.append(1))
    assert called == []  # the solver was never invoked


def test_gate_runs_solver_under_assumption():
    dag = _dag(["T", "Y", "U"], [("U", "T"), ("U", "Y"), ("T", "Y")], ["T", "Y"])
    r = identify(dag, "T", "Y", assume_unconfounded={"U"})
    assert gate(r, lambda: "ok") == "ok"


# ── d-separation correctness ────────────────────────────────────────────────
def test_d_separation_fork_and_chain_and_collider():
    # Fork Z → {X, Y}: X ⊥ Y | Z, not marginally.
    fork = _dag(["X", "Y", "Z"], [("Z", "X"), ("Z", "Y")], ["X", "Y", "Z"])
    assert d_separated(fork, "X", "Y", {"Z"})
    assert not d_separated(fork, "X", "Y", set())

    # Collider X → C ← Y: X ⊥ Y marginally, DEPENDENT given C.
    collider = _dag(["X", "Y", "C"], [("X", "C"), ("Y", "C")], ["X", "Y", "C"])
    assert d_separated(collider, "X", "Y", set())
    assert not d_separated(collider, "X", "Y", {"C"})
