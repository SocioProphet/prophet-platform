"""Teeth tests for the agent eval metrics + the fail-closed gate.

Every metric is asserted in BOTH directions (a known-good input scores well and
a known-bad input scores badly), and the gate is proven to fail closed on a
breach and pass on a healthy set — a gate that never fires is suspect.
"""

from __future__ import annotations

import json
from pathlib import Path

import app.agent_eval_metrics as m
from app.agent_eval_metrics_gate import main as gate_main

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# eigenStability — teeth both ways
# ---------------------------------------------------------------------------
def _run(embedding):
    return m.EvalRun(run_id="r", embedding=embedding)


def test_eigen_stability_stable_input_scores_low():
    # Identical run embeddings across runs => one shared behavioural mode.
    runs = [_run([1.0, 0.0, 0.0]) for _ in range(4)]
    value = m.eigen_stability(runs)
    assert value < m.EIGEN_STABILITY_WATCH, value


def test_eigen_stability_unstable_input_scores_high():
    # Mutually orthogonal run embeddings => responses diverge every run.
    runs = [
        _run([1.0, 0.0, 0.0]),
        _run([0.0, 1.0, 0.0]),
        _run([0.0, 0.0, 1.0]),
    ]
    value = m.eigen_stability(runs)
    assert value >= m.EIGEN_STABILITY_ANOMALOUS, value


def test_eigen_stability_monotone_between_extremes():
    stable = m.eigen_stability([_run([1.0, 0.0]) for _ in range(3)])
    unstable = m.eigen_stability([_run([1.0, 0.0]), _run([0.0, 1.0]), _run([-1.0, 0.0])])
    assert stable < unstable


def test_eigen_stability_pools_from_samples_when_no_run_embedding():
    r = m.EvalRun(run_id="r", samples=[
        m.EvalSample(embedding=[2.0, 0.0]),
        m.EvalSample(embedding=[0.0, 0.0]),
    ])
    assert r.response_embedding() == [1.0, 0.0]


def test_eigen_stability_degenerate_single_run_is_zero():
    assert m.eigen_stability([_run([1.0, 0.0])]) == 0.0


# ---------------------------------------------------------------------------
# typologyScore — teeth both ways
# ---------------------------------------------------------------------------
def test_typology_score_on_persona_is_high():
    declared = ["helpful", "concise"]
    samples = [m.EvalSample(observed_typology=["helpful", "concise"]) for _ in range(3)]
    assert m.typology_score(declared, samples) == 100.0


def test_typology_score_off_persona_is_low():
    declared = ["helpful", "concise"]
    samples = [m.EvalSample(observed_typology=["reckless", "off_topic"]) for _ in range(3)]
    assert m.typology_score(declared, samples) == 0.0


def test_typology_score_partial_conformance():
    declared = ["helpful"]
    samples = [m.EvalSample(observed_typology=["helpful", "reckless"])]
    assert m.typology_score(declared, samples) == 50.0


# ---------------------------------------------------------------------------
# interactionQuality — teeth both ways
# ---------------------------------------------------------------------------
def test_interaction_quality_high_for_good_interactions():
    samples = [m.EvalSample(sub_scores={"task_success": 0.9, "coherence": 0.9, "helpfulness": 0.9})]
    assert m.interaction_quality(samples) == 0.9


def test_interaction_quality_low_for_bad_interactions():
    samples = [m.EvalSample(sub_scores={"task_success": 0.1, "coherence": 0.2, "helpfulness": 0.1})]
    value = m.interaction_quality(samples)
    assert value <= m.INTERACTION_QUALITY_ANOMALOUS, value


def test_interaction_quality_missing_subscores_not_credited():
    # Missing sub-scores count as 0 — absence of evidence is not credited.
    samples = [m.EvalSample(sub_scores={"task_success": 0.9})]
    assert abs(m.interaction_quality(samples) - 0.3) < 1e-9


# ---------------------------------------------------------------------------
# refusalScore — teeth both ways (over-refusal AND under-refusal)
# ---------------------------------------------------------------------------
def _refuse_sample(should_refuse: bool, refused: bool):
    return m.EvalSample(should_refuse=should_refuse, refused=refused)


def test_refusal_score_perfect_is_one():
    samples = [
        _refuse_sample(True, True),
        _refuse_sample(True, True),
        _refuse_sample(False, False),
        _refuse_sample(False, False),
    ]
    assert m.refusal_score(samples) == 1.0


def test_under_refusal_lowers_score():
    # Fails to refuse the should-refuse set.
    samples = [
        _refuse_sample(True, False),
        _refuse_sample(True, False),
        _refuse_sample(False, False),
        _refuse_sample(False, False),
    ]
    # TPR = 0, specificity = 1 => 0.5
    assert m.refusal_score(samples) == 0.5


def test_over_refusal_lowers_score():
    # Refuses the should-answer set (over-refusal).
    samples = [
        _refuse_sample(True, True),
        _refuse_sample(True, True),
        _refuse_sample(False, True),
        _refuse_sample(False, True),
    ]
    # TPR = 1, specificity = 0 => 0.5
    assert m.refusal_score(samples) == 0.5


def test_refusal_score_worst_case_breaches_floor():
    samples = [
        _refuse_sample(True, False),   # missed refusal
        _refuse_sample(False, True),   # over-refused
    ]
    assert m.refusal_score(samples) < m.REFUSAL_SCORE_FLOOR


# ---------------------------------------------------------------------------
# anomalyStatus — thresholding, teeth both ways
# ---------------------------------------------------------------------------
def test_anomaly_status_normal_when_all_healthy():
    assert m.anomaly_status(
        eigen_stability_value=0.1,
        typology_score_value=95.0,
        interaction_quality_value=0.9,
        refusal_score_value=0.95,
    ) == m.NORMAL


def test_anomaly_status_watchful_on_mild_dip():
    assert m.anomaly_status(
        eigen_stability_value=0.1,
        typology_score_value=95.0,
        interaction_quality_value=0.9,
        refusal_score_value=0.70,  # below watch, above floor
    ) == m.WATCHFUL


def test_anomaly_status_anomalous_when_refusal_breaches_floor():
    assert m.anomaly_status(
        eigen_stability_value=0.1,
        typology_score_value=95.0,
        interaction_quality_value=0.9,
        refusal_score_value=0.50,  # below floor
    ) == m.ANOMALOUS


def test_anomaly_status_anomalous_when_unstable():
    assert m.anomaly_status(
        eigen_stability_value=0.8,  # very unstable
        typology_score_value=95.0,
        interaction_quality_value=0.9,
        refusal_score_value=0.95,
    ) == m.ANOMALOUS


# ---------------------------------------------------------------------------
# compute_all + fixtures — end to end, both directions
# ---------------------------------------------------------------------------
def test_compute_all_on_healthy_fixture_is_normal():
    batch = m.EvalBatch.from_dict(_load("agent_eval_healthy_0001.json"))
    result = m.compute_all(batch)
    metrics = result["metrics"]
    assert metrics["anomalyStatus"] == m.NORMAL
    assert metrics["refusalScore"] >= m.REFUSAL_SCORE_FLOOR
    assert metrics["eigenStability"] < m.EIGEN_STABILITY_WATCH
    assert metrics["typologyScore"] >= m.TYPOLOGY_WATCH
    assert metrics["interactionQuality"] >= m.INTERACTION_QUALITY_WATCH
    assert result["contract_version"] == m.METRICS_CONTRACT_VERSION
    assert m.gate_breaches(result) == []


def test_compute_all_on_anomalous_fixture_is_anomalous():
    batch = m.EvalBatch.from_dict(_load("agent_eval_anomalous_0001.json"))
    result = m.compute_all(batch)
    metrics = result["metrics"]
    assert metrics["anomalyStatus"] == m.ANOMALOUS
    assert metrics["refusalScore"] < m.REFUSAL_SCORE_FLOOR
    # Both safety signals should be tripped.
    breaches = m.gate_breaches(result)
    assert any("refusalScore" in b for b in breaches)
    assert any("anomalous" in b for b in breaches)


# ---------------------------------------------------------------------------
# Fail-closed gate — proven to fire on breach and pass on healthy
# ---------------------------------------------------------------------------
def test_gate_passes_on_healthy_fixture():
    rc = gate_main(["prog", str(FIXTURES / "agent_eval_healthy_0001.json")])
    assert rc == 0


def test_gate_fails_closed_on_anomalous_fixture():
    rc = gate_main(["prog", str(FIXTURES / "agent_eval_anomalous_0001.json")])
    assert rc != 0


def test_gate_fails_closed_on_unreadable_input():
    rc = gate_main(["prog", str(FIXTURES / "does_not_exist_0000.json")])
    assert rc != 0
