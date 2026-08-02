"""The capacity guard fails CLOSED on an incomplete estate inventory and never queries
a project-wide datasource unscoped.

Two adversarial-review findings, both about a control reporting headroom it cannot see:

  1. The estate-budget accumulator used to `except Exception: pass`, so a PVC that could
     not be read was silently counted as 0Gi. That undercounts `provisioned`, and the
     aggregate brake (`provisioned - cur + new > budget`) would then pass a grow that
     actually breaches estateMaxTotalGi. The fix: an unreadable PVC makes the total
     UNKNOWN, and an unknown budget refuses every grow this cycle.
  2. The utilisation query was unscoped against Google Managed Prometheus (project-wide),
     so a second cluster's kubelet_volume_stats_* collide on namespace/pvc — a mutating
     guard reading another cluster's fill level. The fix pins cluster (+location).

Local-only (Actions are spend-capped). Requires: python3 (stdlib only) + pytest.
"""
from __future__ import annotations

import importlib.util
import urllib.error
from pathlib import Path

import pytest

_GUARD = Path(__file__).resolve().parents[1] / "base" / "guard.py"


def _load():
    spec = importlib.util.spec_from_file_location("pvc_guard_under_test", _GUARD)
    assert spec and spec.loader, f"cannot import {_GUARD}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pvc(storage: str):
    return {
        "spec": {"resources": {"requests": {"storage": storage}}, "storageClassName": "standard"},
        "metadata": {"annotations": {}},
    }


def test_a_read_error_near_budget_refuses_growth_instead_of_undercounting(monkeypatch):
    """THE regression. Two enrolled PVCs; 'big' is unreadable so the estate total is a
    floor, not the truth. 'small' is over threshold and WOULD grow. Pre-fix the failed
    read was swallowed, `provisioned` undercounted, and the brake let 'small' grow (it
    called grow_pvc). Post-fix the unknown budget refuses the grow and raises
    PvcGuardBudgetUnknown."""
    g = _load()
    policy = {
        "estateMaxTotalGi": 300,
        "defaults": {"thresholdPct": 75, "stepPct": 50, "minStepGi": 5,
                     "maxStepGi": 50, "cooldownMinutes": 30},
        "pvcs": [
            {"namespace": "ns", "name": "big", "maxGi": 500},    # unreadable -> total unknown
            {"namespace": "ns", "name": "small", "maxGi": 500},  # 90% full -> would grow
        ],
    }
    monkeypatch.setattr(g, "load_policy", lambda: policy)
    monkeypatch.setattr(g, "kube_ctx", lambda: ("http://x", {}, None))
    monkeypatch.setattr(g, "utilisation", lambda: {"ns/small": 0.90})
    monkeypatch.setattr(g, "sc_expandable", lambda *a, **k: True)
    monkeypatch.setattr(g, "DRY_RUN", False)

    def fake_get_pvc(base, hdrs, ctx, ns, name):
        if name == "big":
            raise urllib.error.HTTPError("http://x/big", 503, "Service Unavailable", {}, None)
        return _pvc("200Gi")
    monkeypatch.setattr(g, "get_pvc", fake_get_pvc)

    grows: list = []
    monkeypatch.setattr(g, "grow_pvc", lambda *a, **k: grows.append(a))
    alerts: list[str] = []
    monkeypatch.setattr(g, "alert", lambda name, *a, **k: alerts.append(name))

    g.main()

    assert grows == [], (
        "budget was UNKNOWN (an enrolled PVC could not be read) but the guard grew a volume "
        "anyway — the aggregate brake acted on an undercounted total")
    assert "PvcGuardBudgetUnknown" in alerts, "the blind-budget refusal must be alerted, not silent"
    assert "PvcGuardExpanded" not in alerts, "nothing should have been grown this cycle"


def test_utilisation_query_is_pinned_to_this_cluster(monkeypatch):
    """The mutating guard must scope its project-wide GMP query to this cluster. Pre-fix
    the query was bare `kubelet_volume_stats_used_bytes / ..._capacity_bytes`; post-fix
    both operands carry cluster (+location) matchers."""
    g = _load()
    g.CLUSTER_NAME = "prophet-gke"
    g.CLUSTER_LOCATION = "us-central1"
    captured: dict[str, str] = {}

    def fake_promql(q):
        captured["q"] = q
        return [{"metric": {"namespace": "ns", "persistentvolumeclaim": "p"}, "value": [0, "0.5"]}]
    monkeypatch.setattr(g, "promql", fake_promql)

    g.utilisation()

    q = captured["q"]
    assert q.count('cluster="prophet-gke"') == 2, f"both operands must be cluster-scoped: {q}"
    assert 'location="us-central1"' in q, f"location matcher missing: {q}"


def test_unknown_cluster_scope_fails_closed(monkeypatch):
    """If the cluster cannot be determined at all, refuse to query rather than sweep the
    whole project — an unscoped mutating guard is the collision hazard itself."""
    g = _load()
    g.CLUSTER_NAME = ""
    g.CLUSTER_LOCATION = ""
    monkeypatch.setattr(g, "_metadata_attr", lambda attr: "")   # not on GKE
    called = {"promql": False}
    monkeypatch.setattr(g, "promql", lambda q: called.__setitem__("promql", True) or [])
    with pytest.raises(RuntimeError, match="cluster scope is unknown"):
        g.utilisation()
    assert called["promql"] is False, "must refuse BEFORE issuing an unscoped query"
