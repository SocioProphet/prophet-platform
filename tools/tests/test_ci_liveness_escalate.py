"""Martha measures; Mary escalates. These test the escalating half."""
import json
import subprocess
from types import SimpleNamespace

import pytest

from tools.ci_liveness_escalate import MARKER, age_days, escalate, main, render, tier_for


def alarm(workflow, why, verdict="STALE"):
    return {"repo": "o/r", "workflow": workflow, "verdict": verdict, "why": why}


def test_severity_rises_with_the_age_of_the_silence():
    """The load-bearing property: sitting still makes a finding LOUDER, never quieter."""
    assert tier_for(5)[0] == "P3"
    assert tier_for(31)[0] == "P2"
    assert tier_for(61)[0] == "P1"
    assert tier_for(91)[0] == "P0"


def test_severity_is_monotone_in_age():
    order = {"P3": 0, "P2": 1, "P1": 2, "P0": 3}
    ages = [1, 15, 30, 45, 60, 75, 90, 200]
    sevs = [order[tier_for(a)[0]] for a in ages]
    assert sevs == sorted(sevs), "an older silence must never be quieter"


def test_a_never_green_workflow_outranks_any_age():
    assert age_days("never completed successfully; most recent run concluded 'failure'") == 9999
    assert tier_for(age_days("never completed successfully"))[0] == "P0"


def test_an_undateable_verdict_is_treated_as_maximally_old():
    """A verdict we cannot date is not a verdict we may discount."""
    assert age_days("never executed") == 9999


def test_age_is_read_from_the_sweep_reason():
    assert age_days("last green 67d ago (2026-05-29), outside the 14d window") == 67


def test_the_issue_carries_a_marker_so_it_is_updated_not_duplicated():
    """Alarm spam mutes a channel, and a muted channel is a dead control."""
    _, body, _ = render("o/r", [alarm("CI", "last green 20d ago")], 14)
    assert MARKER in body


def test_the_title_names_severity_and_the_worst_age():
    title, _, label = render("o/r", [alarm("CI", "last green 67d ago"),
                                     alarm("Lint", "last green 3d ago")], 14)
    assert title.startswith("[P1]")
    assert "67d" in title
    assert label == "ci-liveness:P1"


def test_the_worst_workflow_is_listed_first():
    _, body, _ = render("o/r", [alarm("recent", "last green 3d ago"),
                                alarm("ancient", "last green 80d ago")], 14)
    assert body.index("`ancient`") < body.index("`recent`")


def test_the_body_states_why_absence_needs_an_address():
    _, body, _ = render("o/r", [alarm("CI", "last green 20d ago")], 14)
    assert "same observable as a passing build" in body
    assert "absence has an address" in body


def test_it_promises_to_close_itself():
    """An issue that outlives its cause is noise, and noise is what taught everyone to stop reading."""
    _, body, _ = render("o/r", [alarm("CI", "last green 20d ago")], 14)
    assert "closes itself" in body


def test_every_alarm_appears_in_the_table():
    alarms = [alarm(f"wf{i}", f"last green {i * 10}d ago") for i in range(1, 5)]
    _, body, _ = render("o/r", alarms, 14)
    for a in alarms:
        assert f"`{a['workflow']}`" in body


def _fake_gh_that_fails_writes(args, capture_output, text):
    """`gh issue list` (a read) succeeds with no existing issue; every mutating call
    (create/edit/comment/close) fails, as if the token lacked `issues: write` or hit a
    rate limit."""
    if "list" in args:
        return SimpleNamespace(returncode=0, stdout="[]", stderr="")
    return SimpleNamespace(returncode=1, stdout="", stderr="HTTP 403: Resource not accessible")


def test_a_failed_issue_write_raises_instead_of_reporting_success(monkeypatch):
    """The gap this closes: escalate() used to call every mutating `gh` invocation with
    check=False. A real write failure (bad token scope, rate limit, renamed repo) was
    swallowed — the function returned an "opened"/"updated" string regardless, so the sweep
    found an alarm, tried to make it land on someone, silently failed to, and reported
    success. That is exactly the 'silence looks like health' pattern this whole tool exists
    to catch, recreated one level up inside itself. A write failure must raise."""
    monkeypatch.setattr(subprocess, "run", _fake_gh_that_fails_writes)
    with pytest.raises(RuntimeError):
        escalate("o/r", [alarm("CI", "last green 20d ago")], 14)


def test_main_exits_nonzero_when_an_escalation_write_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", _fake_gh_that_fails_writes)
    sweep_json = tmp_path / "sweep.json"
    sweep_json.write_text(json.dumps({
        "window_days": 14,
        "results": [{"repo": "o/r"}],
        "alarms": [alarm("CI", "last green 20d ago")],
    }))
    rc = main(["--sweep-json", str(sweep_json)])
    assert rc == 1, "a repo whose escalation issue failed to write must not exit 0"


def test_main_still_succeeds_when_writes_succeed(monkeypatch, tmp_path):
    """Guards against over-correcting: a clean run (writes succeed, or there's nothing to
    write because the repo is green) must still exit 0."""
    def fake_ok(args, capture_output, text):
        return SimpleNamespace(returncode=0, stdout="[]", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_ok)
    sweep_json = tmp_path / "sweep.json"
    sweep_json.write_text(json.dumps({
        "window_days": 14,
        "results": [{"repo": "o/r"}],
        "alarms": [],
    }))
    rc = main(["--sweep-json", str(sweep_json)])
    assert rc == 0
