#!/usr/bin/env python3
"""The canary-gate validator catches theater: phantom metrics and can't-fail gates."""
import importlib.util
import pathlib

import yaml

_SPEC = importlib.util.spec_from_file_location(
    "vam", pathlib.Path(__file__).resolve().parent / "validate_analysis_metrics.py")
vam = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(vam)


def _write(tmp_path, monkeypatch, template: dict, rules=("job:request_error_ratio:rate5m",)):
    pd = tmp_path / "infra/k8s/progressive-delivery/base"
    pd.mkdir(parents=True)
    (pd / "t.yaml").write_text(yaml.safe_dump(template))
    monkeypatch.setattr(vam, "PD_DIR", tmp_path / "infra/k8s/progressive-delivery")
    monkeypatch.setattr(vam, "defined_recording_rules", lambda: set(rules))
    return vam.validate()


def _tmpl(metrics):
    return {"apiVersion": "argoproj.io/v1alpha1", "kind": "AnalysisTemplate",
            "metadata": {"name": "t"}, "spec": {"metrics": metrics}}


def _metric(name, query, **extra):
    return {"name": name, "provider": {"prometheus": {"query": query}}, **extra}


def test_real_recording_rule_with_failure_condition_passes(tmp_path, monkeypatch):
    errs = _write(tmp_path, monkeypatch, _tmpl([
        _metric("err", 'job:request_error_ratio:rate5m{job="x"}', failureCondition="result[0] >= 0.05")]))
    assert errs == []


def test_phantom_recording_rule_is_caught(tmp_path, monkeypatch):
    errs = _write(tmp_path, monkeypatch, _tmpl([
        _metric("p", 'job:does_not_exist:rate5m{job="x"}', failureCondition="result[0] > 1")]))
    assert any("phantom metric" in e for e in errs)


def test_gate_with_no_failure_path_is_caught(tmp_path, monkeypatch):
    errs = _write(tmp_path, monkeypatch, _tmpl([
        _metric("nofail", 'job:request_error_ratio:rate5m{job="x"}')]))  # no failureCondition/Limit
    assert any("never fail" in e for e in errs)


def test_failure_limit_counts_as_a_failure_path(tmp_path, monkeypatch):
    errs = _write(tmp_path, monkeypatch, _tmpl([
        _metric("ok", 'job:request_error_ratio:rate5m{job="x"}', failureLimit=1)]))
    assert errs == []


def test_template_with_no_metrics_is_caught(tmp_path, monkeypatch):
    errs = _write(tmp_path, monkeypatch, _tmpl([]))
    assert any("no metrics" in e for e in errs)
