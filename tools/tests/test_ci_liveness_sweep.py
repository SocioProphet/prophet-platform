"""The classifier must catch the failure that actually happened, not just the obvious one."""
from datetime import datetime, timedelta, timezone

import pytest

from tools.ci_liveness_sweep import DEAD, OK, SILENT, STALE, classify

NOW = datetime(2026, 8, 4, tzinfo=timezone.utc)


def iso(days_ago: int) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")


def run(conclusion: str, days_ago: int) -> dict:
    return {"conclusion": conclusion, "updated_at": iso(days_ago)}


def test_recent_green_is_ok():
    v, _ = classify(iso(2), run("success", 2), window_days=14, now=NOW)
    assert v == OK


def test_the_goose_notes_case_is_SILENT_not_ok():
    """The five-week failure: runs EXIST so the pipeline looks alive, and none of them succeed.

    goose-notes CI reported `startup_failure` in 0s on every push from 2026-07-01. A checker that
    only asked "did it run?" would have said yes every single day.
    """
    v, why = classify(iso(34), run("startup_failure", 0), window_days=14, now=NOW)
    assert v == SILENT
    assert "not succeeding" in why


def test_a_pipeline_that_never_worked_is_DEAD():
    v, why = classify(None, run("failure", 1), window_days=14, now=NOW)
    assert v == DEAD
    assert "never completed successfully" in why


def test_no_runs_at_all_is_DEAD():
    v, why = classify(None, None, window_days=14, now=NOW)
    assert v == DEAD
    assert "never executed" in why


def test_abandoned_but_once_green_is_STALE():
    """Succeeded long ago, nothing since — quietly abandoned rather than actively broken."""
    v, why = classify(iso(90), run("success", 90), window_days=14, now=NOW)
    assert v == STALE
    assert "90d ago" in why


def test_green_exactly_at_the_window_edge_is_ok():
    v, _ = classify(iso(14), run("success", 14), window_days=14, now=NOW)
    assert v == OK


def test_one_day_past_the_window_alarms():
    v, _ = classify(iso(15), run("success", 15), window_days=14, now=NOW)
    assert v in (STALE, SILENT)


def test_a_recent_failure_does_not_mask_a_recent_success():
    """Red today is fine if green happened inside the window — this alarms on ABSENCE of green,
    not on presence of red. Flaky is a different problem from dead."""
    v, _ = classify(iso(3), run("failure", 0), window_days=14, now=NOW)
    assert v == OK


def test_every_alarm_states_a_reason():
    for args in [(None, None), (None, run("failure", 1)),
                 (iso(34), run("startup_failure", 0)), (iso(90), run("success", 90))]:
        v, why = classify(*args, window_days=14, now=NOW)
        assert v != OK and len(why) > 20, args


# --- precision: a checker that cries wolf gets muted, and a muted control is a dead one --------

def test_a_never_invoked_dispatch_workflow_is_UNUSED_not_dead():
    from tools.ci_liveness_sweep import UNUSED
    v, why = classify(None, None, window_days=14, now=NOW, dispatch_only=True)
    assert v == UNUSED and "not broken" in why


def test_a_never_invoked_AUTOMATIC_workflow_is_still_DEAD():
    v, _ = classify(None, None, window_days=14, now=NOW, dispatch_only=False)
    assert v == DEAD


def test_a_dispatch_workflow_that_FAILED_is_still_DEAD():
    """Never invoked is benign. Invoked and never succeeded is not."""
    v, why = classify(None, run("failure", 5), window_days=14, now=NOW, dispatch_only=True)
    assert v == DEAD and "never completed successfully" in why


def test_an_idle_dispatch_workflow_is_UNUSED_not_stale():
    from tools.ci_liveness_sweep import UNUSED
    v, why = classify(iso(60), run("success", 60), window_days=14, now=NOW, dispatch_only=True)
    assert v == UNUSED and "idle by design" in why


def test_an_in_progress_first_run_is_not_called_dead():
    from tools.ci_liveness_sweep import UNUSED
    v, _ = classify(None, {"conclusion": None, "updated_at": iso(0)}, window_days=14, now=NOW)
    assert v == UNUSED


def test_UNUSED_never_alarms():
    from tools.ci_liveness_sweep import ALARM_VERDICTS, UNUSED
    assert UNUSED not in ALARM_VERDICTS


def test_no_runs_is_never_reported_as_in_progress():
    """Regression: a jq precedence bug made `{conclusion,updated_at} // empty` build an object from
    a null run, so 'no runs at all' surfaced as 'a run with no conclusion'. Three BearBrowser
    signing workflows were misreported as 'still in progress' simultaneously, which is what gave it
    away. `latest=None` must reach the DEAD/UNUSED branch, never the in-progress one."""
    v, why = classify(None, None, window_days=14, now=NOW, dispatch_only=False)
    assert v == DEAD and "never executed" in why
    assert "in progress" not in why


# --- path-filtered controls: quiet is not broken, but it is worth saying --------------------

def test_a_path_filtered_workflow_that_always_passed_is_not_stale():
    """BearBrowser's Browser Runtime Boundary: every run succeeded, and it had not fired in 67 days
    because nobody touched its paths. Calling that STALE is a false positive, and false positives
    are how a checker gets muted."""
    from tools.ci_liveness_sweep import ON_CHANGE
    v, why = classify(iso(67), run("success", 67), window_days=14, now=NOW, path_filtered=True)
    assert v == ON_CHANGE
    assert "NOT broken" in why


def test_but_it_still_names_the_real_gap():
    """It never re-validates: environment drift passes unnoticed underneath it."""
    from tools.ci_liveness_sweep import ON_CHANGE
    _, why = classify(iso(67), run("success", 67), window_days=14, now=NOW, path_filtered=True)
    assert "never re-validates" in why and "schedule:" in why


def test_a_scheduled_path_filtered_workflow_IS_stale_when_silent():
    """If it has a `schedule:` it should be firing regardless of file changes — so silence is real."""
    v, _ = classify(iso(67), run("success", 67), window_days=14, now=NOW,
                    path_filtered=True, scheduled=True)
    assert v == STALE


def test_ON_CHANGE_ONLY_does_not_alarm():
    from tools.ci_liveness_sweep import ALARM_VERDICTS, ON_CHANGE
    assert ON_CHANGE not in ALARM_VERDICTS


def test_an_unfiltered_workflow_silent_for_months_is_still_stale():
    v, _ = classify(iso(67), run("success", 67), window_days=14, now=NOW, path_filtered=False)
    assert v == STALE
