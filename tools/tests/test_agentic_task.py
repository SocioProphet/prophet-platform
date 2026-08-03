"""AgenticTask state machine — fail-closed lifecycle, risk->approval, typed
interrupts (critical-only focus), seal + tamper detection. Offline."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import agentic_task as at  # noqa: E402
from validate_agentic_task import semantic_checks, validate_interrupt  # noqa: E402
import pytest  # noqa: E402


def test_legal_lifecycle_and_seal():
    t = at.new_task("audit repos", owner="human:x", autonomy_level="L2")
    assert t["state"] == "drafting" and at.verify_seal(t)
    at.transition(t, "ready"); at.transition(t, "running")
    at.transition(t, "waiting_for_approval"); at.transition(t, "completed")
    assert t["state"] == "completed"
    assert semantic_checks(t) == []


def test_illegal_transition_fails_closed():
    t = at.new_task("g", owner="o")
    at.transition(t, "ready"); at.transition(t, "running")
    with pytest.raises(at.TaskError):
        at.transition(t, "drafting")  # not a legal successor of running


def test_low_risk_autostages_high_derives_approval():
    t = at.new_task("g", owner="o")
    lo = at.add_action(t, "issue.draft", "low", why="reversible")
    assert lo["state"] == "staged"
    assert t["approval_requirements"] == {"tier": "low", "requires_human": False,
                                          "reason": at._APPROVAL_REASON["low"]}
    hi = at.add_action(t, "config.prod-change", "high", why="prod impact")
    assert hi["state"] == "proposed"
    assert t["approval_requirements"]["tier"] == "high"
    assert t["approval_requirements"]["requires_human"] is True


def test_action_lifecycle():
    t = at.new_task("g", owner="o")
    a = at.add_action(t, "mr.open", "medium", why="touches build config")  # -> proposed
    with pytest.raises(at.TaskError):
        at.transition_action(t, a["action_id"], "approved")  # must be STAGED first
    at.transition_action(t, a["action_id"], "staged")
    at.transition_action(t, a["action_id"], "approved")
    at.transition_action(t, a["action_id"], "executing")
    at.transition_action(t, a["action_id"], "succeeded")
    with pytest.raises(at.TaskError):
        at.transition_action(t, a["action_id"], "executing")  # succeeded is not a predecessor


def test_action_requires_why():
    t = at.new_task("g", owner="o")
    with pytest.raises(at.TaskError):
        at.add_action(t, "x", "low", why="")


def test_typed_interrupt_focus_rule():
    t = at.new_task("g", owner="o")
    fyi = at.make_interrupt(t, "fyi", "heads up")
    crit = at.make_interrupt(t, "critical", "prod down")
    assert fyi["invades_focus"] is False and crit["invades_focus"] is True
    assert validate_interrupt(fyi) == [] and validate_interrupt(crit) == []
    # a hand-forged non-critical claiming focus is rejected
    assert validate_interrupt({"type": "fyi", "invades_focus": True})


def test_tamper_detected():
    t = at.new_task("g", owner="o")
    t["goal"] = "tampered"
    assert "hash seal does not verify" in semantic_checks(t)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
