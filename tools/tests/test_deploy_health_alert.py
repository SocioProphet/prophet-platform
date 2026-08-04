"""Negative control for the deploy-health alerter.

The whole point of this tool is to FIRE on a runtime gap that static gates miss.
So the thing under test is that its classifier DISCRIMINATES — flags the broken,
passes the healthy — and that its orchestration fails closed (an unobservable
scan is exit 2, never a green 0). A gate proven only on the happy path is exactly
the paper control this tool exists to catch.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import deploy_health_alert as dha  # noqa: E402


# ── ArgoCD app classification ────────────────────────────────────────────────
def test_healthy_synced_app_is_clean():
    assert dha.classify_app({"status": {"health": {"status": "Healthy"},
                                        "sync": {"status": "Synced"}}}) == []


def test_degraded_app_is_flagged():
    # the arcticdb-gateway case: Degraded for 20h while static gates stayed green
    assert dha.classify_app({"status": {"health": {"status": "Degraded"},
                                        "sync": {"status": "Synced"}}}) == ["health=Degraded"]


def test_missing_and_unknown_health_flagged():
    for h in ("Missing", "Unknown"):
        assert f"health={h}" in dha.classify_app({"status": {"health": {"status": h}}})


def test_outofsync_flagged_but_ignorable():
    app = {"status": {"health": {"status": "Healthy"}, "sync": {"status": "OutOfSync"}}}
    assert "sync=OutOfSync" in dha.classify_app(app)
    assert dha.classify_app(app, ignore_sync=True) == []


def test_app_with_no_status_is_unknown_not_silently_clean():
    # a control must not read "no data" as "healthy"
    assert dha.classify_app({}) == ["health=Unknown"]


# ── pod classification ───────────────────────────────────────────────────────
def test_running_pod_is_clean():
    pod = {"status": {"phase": "Running", "containerStatuses": [
        {"name": "c", "state": {"running": {}}, "restartCount": 0}]}}
    assert dha.classify_pod(pod, restart_threshold=5) == []


def test_every_stuck_waiting_reason_is_flagged():
    for reason in dha.STUCK_WAITING:
        pod = {"status": {"phase": "Pending", "containerStatuses": [
            {"name": "c", "state": {"waiting": {"reason": reason}}, "restartCount": 0}]}}
        assert dha.classify_pod(pod, restart_threshold=5) == [f"c:{reason}"]


def test_benign_waiting_reason_not_flagged():
    # ContainerCreating / PodInitializing are normal startup, not a gap
    for reason in ("ContainerCreating", "PodInitializing"):
        pod = {"status": {"phase": "Pending", "containerStatuses": [
            {"name": "c", "state": {"waiting": {"reason": reason}}, "restartCount": 0}]}}
        assert dha.classify_pod(pod, restart_threshold=5) == []


def test_high_restarts_flagged_at_threshold():
    pod = {"status": {"phase": "Running", "containerStatuses": [
        {"name": "c", "state": {"running": {}}, "restartCount": 5}]}}
    assert dha.classify_pod(pod, restart_threshold=5) == ["c:restarts=5"]
    assert dha.classify_pod(pod, restart_threshold=6) == []


def test_terminating_and_succeeded_pods_ignored():
    terminating = {"metadata": {"deletionTimestamp": "t"}, "status": {"phase": "Running",
        "containerStatuses": [{"name": "c", "state": {"waiting": {"reason": "CrashLoopBackOff"}}}]}}
    succeeded = {"status": {"phase": "Succeeded", "containerStatuses": [
        {"name": "c", "state": {"terminated": {"reason": "Completed"}}, "restartCount": 0}]}}
    assert dha.classify_pod(terminating, restart_threshold=1) == []
    assert dha.classify_pod(succeeded, restart_threshold=1) == []


# ── job-receipt staleness (the generalized backup honesty fix) ───────────────
NOW = 1_000_000.0


def test_fresh_successful_receipt_is_clean():
    assert dha.classify_receipt({"job": "backup", "ts": NOW - 60, "rc": 0},
                                now_epoch=NOW, max_age_s=3600) == []


def test_stale_receipt_flagged():
    # backup stuck at 2026-07-30: the job stopped running; the receipt went stale
    out = dha.classify_receipt({"job": "backup", "ts": NOW - 100000, "rc": 0},
                               now_epoch=NOW, max_age_s=3600)
    assert any("stale" in r for r in out)


def test_failed_receipt_flagged():
    # backup exited non-zero but launchd saw green: rc must be read, not assumed
    assert "rc=2" in dha.classify_receipt({"job": "backup", "ts": NOW - 60, "rc": 2},
                                          now_epoch=NOW, max_age_s=3600)


def test_missing_receipt_is_the_strongest_signal():
    assert dha.classify_receipt(None, now_epoch=NOW, max_age_s=3600) != []


def test_iso_and_epoch_timestamps_both_parse():
    from datetime import datetime, timezone
    iso = datetime.fromtimestamp(NOW - 60, timezone.utc).isoformat()
    assert dha.classify_receipt({"ts": iso, "rc": 0}, now_epoch=NOW, max_age_s=3600) == []
    assert dha.classify_receipt({"ts": NOW - 60, "rc": 0}, now_epoch=NOW, max_age_s=3600) == []
    assert dha._to_epoch("not-a-date") is None


# ── fail-closed orchestration: unobservable ≠ healthy ────────────────────────
def _args(**kw):
    import argparse
    base = dict(namespace="x", argocd_namespace="argocd", no_pods=False, no_argocd=False,
                ignore_sync=False, restart_threshold=8, receipts=None, expect=[],
                max_receipt_age=93600, allow_blind=False, json=False, self_test=False)
    base.update(kw)
    return argparse.Namespace(**base)


def test_blind_scan_exits_2_not_0(monkeypatch):
    # kubectl returns None (no access / wrong context) → could-not-observe, not clean
    monkeypatch.setattr(dha, "collect_apps", lambda ns: None)
    monkeypatch.setattr(dha, "collect_pods", lambda ns: None)
    code, report = dha.run(_args())
    assert code == dha.EXIT_BLIND
    assert report["blind"]


def test_empty_cluster_is_blind_not_clean(monkeypatch):
    # zero apps/pods found is "couldn't see anything", not "everything's healthy"
    monkeypatch.setattr(dha, "collect_apps", lambda ns: [])
    monkeypatch.setattr(dha, "collect_pods", lambda ns: [])
    code, _ = dha.run(_args())
    assert code == dha.EXIT_BLIND


def test_healthy_cluster_exits_clean(monkeypatch):
    monkeypatch.setattr(dha, "collect_apps", lambda ns: [
        {"metadata": {"name": "a"}, "status": {"health": {"status": "Healthy"},
                                               "sync": {"status": "Synced"}}}])
    monkeypatch.setattr(dha, "collect_pods", lambda ns: [
        {"metadata": {"name": "p"}, "status": {"phase": "Running", "containerStatuses": [
            {"name": "c", "state": {"running": {}}, "restartCount": 0}]}}])
    code, report = dha.run(_args())
    assert code == dha.EXIT_CLEAN and report["gapCount"] == 0


def test_one_degraded_app_exits_gaps(monkeypatch):
    monkeypatch.setattr(dha, "collect_apps", lambda ns: [
        {"metadata": {"name": "arcticdb-gateway"},
         "status": {"health": {"status": "Degraded"}, "sync": {"status": "Synced"}}}])
    monkeypatch.setattr(dha, "collect_pods", lambda ns: [
        {"metadata": {"name": "p"}, "status": {"phase": "Running", "containerStatuses": [
            {"name": "c", "state": {"running": {}}, "restartCount": 0}]}}])
    code, report = dha.run(_args())
    assert code == dha.EXIT_GAPS
    assert report["findings"][0]["name"] == "arcticdb-gateway"


def test_blind_dominates_gaps(monkeypatch):
    # if we found a gap AND couldn't observe something else, the blind spot wins (2 > 1)
    monkeypatch.setattr(dha, "collect_apps", lambda ns: None)
    monkeypatch.setattr(dha, "collect_pods", lambda ns: [
        {"metadata": {"name": "p"}, "status": {"phase": "Pending", "containerStatuses": [
            {"name": "c", "state": {"waiting": {"reason": "ImagePullBackOff"}}}]}}])
    code, _ = dha.run(_args())
    assert code == dha.EXIT_BLIND


def test_expected_but_absent_receipt_is_a_gap(tmp_path, monkeypatch):
    monkeypatch.setattr(dha, "collect_apps", lambda ns: [
        {"metadata": {"name": "a"}, "status": {"health": {"status": "Healthy"},
                                               "sync": {"status": "Synced"}}}])
    monkeypatch.setattr(dha, "collect_pods", lambda ns: [
        {"metadata": {"name": "p"}, "status": {"phase": "Running", "containerStatuses": [
            {"name": "c", "state": {"running": {}}, "restartCount": 0}]}}])
    code, report = dha.run(_args(receipts=str(tmp_path), expect=["nightly-backup"]))
    assert code == dha.EXIT_GAPS
    assert any(f["name"] == "nightly-backup" and "missing" in f["reason"]
               for f in report["findings"])
