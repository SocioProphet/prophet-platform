"""The census is the meta-control: it must correctly tell a control that CAN fail from one that
can't, and its --fail-on-undiscriminating gate must actually trip on a scheduled control with no
negative control. Tested on synthetic trees so it never depends on the live repo's current state."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import controls_census as cc  # noqa: E402


def _mk_cronjob(root: Path, name: str, *, script_selftest: bool, rule: bool, app: bool):
    base = root / "infra" / "k8s" / name / "base"
    base.mkdir(parents=True)
    (base / "cronjob.yaml").write_text("kind: CronJob\n")
    (base / f"{name}.py").write_text("def _self_test(): ...\n" if script_selftest else "x = 1\n")
    if rule:
        (base / "prometheusrule-guard.yaml").write_text("kind: PrometheusRule\n")
    if app:
        (root / "deploy" / "argocd").mkdir(parents=True, exist_ok=True)
        (root / "deploy" / "argocd" / f"{name}.yaml").write_text("kind: Application\n")


def test_discriminates_via_inline_selftest(tmp_path):
    s = tmp_path / "v.py"; s.write_text("def _self_test():\n return True\n")
    assert cc._discriminates(s) is True


def test_discriminates_via_colocated_test_file(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_v.py").write_text("def test_x(): assert True\n")
    s = tmp_path / "v.py"; s.write_text("x = 1\n")  # no inline marker
    assert cc._discriminates(s) is True


def test_non_discriminating_script(tmp_path):
    s = tmp_path / "v.py"; s.write_text("print('ok')\n")
    assert cc._discriminates(s) is False


def test_meta_monitored_matches_any_prometheusrule_name(tmp_path):
    b = tmp_path; (b / "prometheusrule-guard.yaml").write_text("x")
    assert cc._meta_monitored(b) is True
    assert cc._meta_monitored(tmp_path / "empty") is False


def test_scheduled_control_enumerated_with_properties(tmp_path):
    _mk_cronjob(tmp_path, "good-guard", script_selftest=True, rule=True, app=True)
    ctrls = cc.scheduled_controls(tmp_path)
    assert len(ctrls) == 1
    c = ctrls[0]
    assert c["control"] == "good-guard" and c["discriminates"] and c["meta_monitored"] and c["gitops_app"]


def test_fail_gate_trips_on_undiscriminating_scheduled_control(tmp_path, monkeypatch, capsys):
    _mk_cronjob(tmp_path, "blind-guard", script_selftest=False, rule=False, app=False)
    monkeypatch.setattr(cc, "ROOT", tmp_path)
    # a scheduled control that cannot be shown to fail must fail the gate
    assert cc.main(["--fail-on-undiscriminating"]) == 1
    assert "blind-guard" in capsys.readouterr().out


def test_gate_passes_when_scheduled_control_discriminates(tmp_path, monkeypatch):
    _mk_cronjob(tmp_path, "good-guard", script_selftest=True, rule=True, app=True)
    monkeypatch.setattr(cc, "ROOT", tmp_path)
    assert cc.main(["--fail-on-undiscriminating"]) == 0
