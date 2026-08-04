"""Martha measures; Mary escalates. These test the escalating half."""
import pytest

from tools.ci_liveness_escalate import MARKER, age_days, render, tier_for


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
