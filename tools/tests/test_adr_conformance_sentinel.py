#!/usr/bin/env python3
"""Tests for Firewall #2 — the control-of-controls (meta-meta, second derivative, self-fixpoint)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import adr_conformance_sentinel as s  # noqa: E402

_FULL = {k: True for k in s.FIREWALL1_REQUIREMENTS}


def test_audit_adr_flags_a_missing_firewall1_requirement():
    assert s.audit_adr("A", _FULL)["guarded"] is True
    a = s.audit_adr("B", {"dependency_graph": True, "wave1_prevent": True})  # no wave2/enforcement
    assert a["guarded"] is False and "enforcement" in a["missing"] and "wave2_heal" in a["missing"]


def test_registry_audit_reports_coverage_and_unguarded():
    reg = [{"adr_id": "A", "apparatus": _FULL}, {"adr_id": "B", "apparatus": {}}]
    r = s.audit_registry(reg)
    assert r["total"] == 2 and r["guarded"] == 1 and r["coverage"] == 0.5
    assert [u["adr_id"] for u in r["unguarded"]] == ["B"]


def test_second_derivative_flags_accelerating_gap():
    # gap 0 -> 2 -> 6: d1 = [2,4], d2 = 2 > 0 -> accelerating (the alarm)
    d = s.second_derivative([{"decisions": 3, "controls": 3}, {"decisions": 6, "controls": 4},
                             {"decisions": 11, "controls": 5}])
    assert d["trend"] == "accelerating" and d["d2"] == 2


def test_second_derivative_sees_a_closing_gap():
    # gap 2 -> 1 -> 0: d1 = [-1,-1], d2 = 0, last d1 < 0 -> closing
    d = s.second_derivative([{"decisions": 11, "controls": 9}, {"decisions": 12, "controls": 11},
                             {"decisions": 13, "controls": 13}])
    assert d["trend"] == "closing"


def test_second_derivative_needs_history():
    assert s.second_derivative([{"decisions": 1, "controls": 0}])["trend"] == "insufficient-history"


def test_self_governed_is_the_fixpoint():
    assert s.self_governed([{"control": "adr_conformance_sentinel", "guarded": True}]) is True
    assert s.self_governed([{"control": "adr_conformance_sentinel", "guarded": False}]) is False
    assert s.self_governed([]) is False  # exempting itself = ungoverned


def test_run_failcloses_on_unguarded_adr():
    d = s.run(adr_registry=[{"adr_id": "ADR-0001", "apparatus": {}}], series=[],
              control_registry=[{"control": "adr_conformance_sentinel", "guarded": True}])
    assert d["ok"] is False and "unguarded" in d["alarm"]
    assert d["receipt_digest"].startswith("sha256:")


def test_run_failcloses_when_sentinel_not_self_governed():
    d = s.run(adr_registry=[{"adr_id": "ADR-0001", "apparatus": _FULL}], series=[],
              control_registry=[])  # sentinel absent from its own registry
    assert d["ok"] is False and "self-governed" in d["alarm"]


def test_run_ok_when_guarded_selfgoverned_and_gap_not_accelerating():
    d = s.run(adr_registry=[{"adr_id": "ADR-0001", "apparatus": _FULL}],
              series=[{"decisions": 11, "controls": 9}, {"decisions": 12, "controls": 11},
                      {"decisions": 13, "controls": 13}],
              control_registry=[{"control": "adr_conformance_sentinel", "guarded": True}])
    assert d["ok"] is True and d["alarm"] is None


def test_run_raises_alarm_on_accelerating_gap_even_when_guarded():
    d = s.run(adr_registry=[{"adr_id": "ADR-0001", "apparatus": _FULL}],
              series=[{"decisions": 3, "controls": 3}, {"decisions": 6, "controls": 4},
                      {"decisions": 11, "controls": 5}],
              control_registry=[{"control": "adr_conformance_sentinel", "guarded": True}])
    assert d["ok"] is True and "ACCELERATING" in d["alarm"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"ok: {len(fns)} sentinel tests passed")
    sys.exit(0)
