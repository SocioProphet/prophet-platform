"""The core thesis under test: the fabric catches the SILENT failure, and the authored fix moves the SLO."""
from __future__ import annotations

import dataclasses

from reasoning_failure_runner.engine import run_experiment
from reasoning_failure_runner.suites import BUILTIN_SUITES, SYNTHETIC_TASKS
from reasoning_failure_runner.domain import Verdict


def _with_target(suite_id: str, target: str):
    s = BUILTIN_SUITES[suite_id].model_copy(deep=True)
    s.target = target
    return s


def test_naive_empty200_produces_silent_failures():
    roll = run_experiment(BUILTIN_SUITES["suite:tool-empty-200"], SYNTHETIC_TASKS)
    # naive fabricates on empty results → every run is a WRONG + UNFLAGGED = silent failure
    assert roll.silent_failure_rate == 1.0
    assert roll.verdicts[Verdict.bad.value] == roll.n
    assert roll.completion_after == 0.0
    assert roll.slo_held is False
    assert roll.passed is False


def test_hardened_empty200_recovers_and_moves_the_slo():
    roll = run_experiment(_with_target("suite:tool-empty-200", "hardened"), SYNTHETIC_TASKS)
    # the authored fix: retry the empty result → correct answer, recovered, zero silent failures
    assert roll.silent_failure_rate == 0.0
    assert roll.completion_after == 1.0
    assert roll.recovered_rate == 1.0
    assert roll.slo_held is True
    assert roll.passed is True


def test_plausible_wrong_naive_is_silent_hardened_is_flagged():
    naive = run_experiment(BUILTIN_SUITES["suite:tool-plausible-wrong"], SYNTHETIC_TASKS)
    assert naive.silent_failure_rate == 1.0            # trusts the wrong answer, no flag
    hardened = run_experiment(_with_target("suite:tool-plausible-wrong", "hardened"), SYNTHETIC_TASKS)
    # hardened can't ground it → abstains (a FLAGGED 'sad'), so NOT a silent failure even though incomplete
    assert hardened.silent_failure_rate == 0.0
    assert hardened.verdicts[Verdict.sad.value] == hardened.n
    assert hardened.slo_held is False                  # honest abstention still misses the goal — that's correct


def test_poisoned_chunk_commons_regression():
    # naive serves the planted injection alongside the correct answer → revoked-not-served violated, unflagged
    naive = run_experiment(BUILTIN_SUITES["suite:retrieval-poisoned-chunk"], SYNTHETIC_TASKS)
    assert naive.silent_failure_rate == 1.0
    assert naive.verdicts[Verdict.bad.value] == naive.n
    # hardened strips the marker → correct AND safe
    hardened = run_experiment(_with_target("suite:retrieval-poisoned-chunk", "hardened"), SYNTHETIC_TASKS)
    assert hardened.silent_failure_rate == 0.0
    assert hardened.passed is True


def test_receipts_are_hashed_and_typed():
    roll = run_experiment(BUILTIN_SUITES["suite:tool-empty-200"], SYNTHETIC_TASKS)
    assert roll.n == len(SYNTHETIC_TASKS)
    for r in roll.receipts:
        assert r.receipt_hash.startswith("sha256:")
        assert r.plane.value == "tool"
        assert r.record_type == "ResilienceReceipt"


def test_empty_cohort_is_refused():
    import pytest
    s = BUILTIN_SUITES["suite:tool-empty-200"].model_copy(deep=True)
    s.cohort.sample_rate = 0.0
    with pytest.raises(ValueError):
        run_experiment(s, SYNTHETIC_TASKS)
