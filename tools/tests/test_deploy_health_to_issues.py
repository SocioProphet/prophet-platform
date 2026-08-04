"""Tests for deploy_health_to_issues — the deploy-health → GitHub-issue reconciler.

The reconciler's whole value is that it discriminates: a new gap opens an issue, a
cleared gap closes ITS issue, a chronic gap stays as one issue (no spam), a human's
issue is never touched, and — the load-bearing safety property — a BLIND scan closes
nothing. These tests pin exactly those distinctions.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import deploy_health_to_issues as m  # noqa: E402


CALDAV = {"kind": "argocd-app", "name": "ws-workspace-caldav", "reason": "sync=OutOfSync (sync failing)"}
CALDAV_ISSUE = {"number": 42, "title": "[deploy-health] argocd-app/ws-workspace-caldav"}
STALE_ISSUE = {"number": 7, "title": "[deploy-health] pod/gone-away"}
HUMAN_ISSUE = {"number": 9, "title": "please look at deploy-health someday"}


def test_new_gap_creates():
    plan = m.reconcile([CALDAV], [], blind=False)
    assert [c["key"] for c in plan["create"]] == ["argocd-app/ws-workspace-caldav"]
    assert plan["close"] == [] and plan["keep"] == []


def test_existing_gap_is_kept_not_recreated():
    plan = m.reconcile([CALDAV], [CALDAV_ISSUE], blind=False)
    assert plan["create"] == []
    assert [k["number"] for k in plan["keep"]] == [42]


def test_cleared_gap_closes_its_issue():
    plan = m.reconcile([], [CALDAV_ISSUE], blind=False)
    assert [c["number"] for c in plan["close"]] == [42]


def test_two_reasons_one_workload_is_one_issue():
    pod = [
        {"kind": "pod", "name": "sherlock-x", "reason": "svc:CrashLoopBackOff"},
        {"kind": "pod", "name": "sherlock-x", "reason": "svc:restarts=10"},
    ]
    plan = m.reconcile(pod, [], blind=False)
    assert len(plan["create"]) == 1
    assert sorted(plan["create"][0]["reasons"]) == ["svc:CrashLoopBackOff", "svc:restarts=10"]


def test_blind_never_closes():
    # The invariant that would have prevented silently "resolving" the 40h workspace trap
    # had the scan gone blind: could-not-observe must not be read as all-clear.
    plan = m.reconcile([], [CALDAV_ISSUE, STALE_ISSUE], blind=True)
    assert plan["close"] == []


def test_human_issue_is_never_closed():
    plan = m.reconcile([], [HUMAN_ISSUE], blind=False)
    assert plan["close"] == []


def test_mixed_one_clears_one_persists():
    plan = m.reconcile([CALDAV], [CALDAV_ISSUE, STALE_ISSUE], blind=False)
    assert [c["number"] for c in plan["close"]] == [7]
    assert [k["number"] for k in plan["keep"]] == [42]


def test_title_key_roundtrip():
    assert m.key_from_title(m.title_for("pod/foo")) == "pod/foo"
    assert m.key_from_title("investigate deploy-health") is None
    assert m.key_from_title("[deploy-health] ") is None  # empty key is not owned


def test_body_is_greppable_and_names_the_workload():
    body = m.issue_body("argocd-app/ws-workspace-caldav", ["sync failing"], now_iso="2026-08-04T00:00:00Z")
    assert "deploy-health-key: argocd-app/ws-workspace-caldav" in body
    assert "ws-workspace-caldav" in body


def test_self_test_passes():
    assert m._self_test() == 0


def test_cli_blind_report_refuses(tmp_path):
    """A blind report through the CLI exits 2 (refuse) and closes nothing."""
    rep = tmp_path / "r.json"
    rep.write_text(json.dumps({"exit": 2, "blind": ["pods in ns/x"], "findings": []}))
    r = subprocess.run([sys.executable, str(Path(m.__file__)), "--report", str(rep), "--dry-run"],
                       capture_output=True, text=True)
    assert r.returncode == m.EXIT_BLIND
    assert json.loads(r.stdout)["blind"] is True


def test_cli_non_json_is_blind_not_clean(tmp_path):
    """Garbage input must be treated as blind (exit 2), never as a clean 'no findings'."""
    rep = tmp_path / "r.json"
    rep.write_text("not json at all")
    r = subprocess.run([sys.executable, str(Path(m.__file__)), "--report", str(rep)],
                       capture_output=True, text=True)
    assert r.returncode == m.EXIT_BLIND


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
