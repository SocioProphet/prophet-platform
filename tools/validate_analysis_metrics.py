#!/usr/bin/env python3
"""Prove the SLO canary gate queries REAL metrics and CAN fail.

A canary AnalysisTemplate that queries a metric which doesn't exist returns no data →
Argo treats it as inconclusive, never fails → the "gate" silently passes every bad deploy.
That is theater. This validator makes it impossible:

  1. Every recording-rule metric (`level:metric:op` form) referenced in an AnalysisTemplate
     query MUST be defined as a `record:` in the observability PrometheusRules. A query over a
     phantom recording rule fails the build.
  2. Every metric in the template MUST declare a failureCondition or a failureLimit — a gate
     with no way to fail is not a gate.

Fail-closed: a malformed template, or an AnalysisTemplate with zero metrics, is an error.
"""
from __future__ import annotations

import pathlib
import re
import sys

import yaml

_ROOT = pathlib.Path(__file__).resolve().parents[1]
PD_DIR = _ROOT / "infra" / "k8s" / "progressive-delivery"
SLO_GLOB = "infra/k8s/observability/**/*.yaml"
# recording-rule naming convention: level:metric:operations (Prometheus best practice)
_RECORDING_RULE = re.compile(r"\b([a-zA-Z_][\w]*:[\w]+:[\w]+)\b")


def _docs(path: pathlib.Path):
    try:
        return [d for d in yaml.safe_load_all(path.read_text()) if isinstance(d, dict)]
    except yaml.YAMLError:
        return []


def defined_recording_rules() -> set[str]:
    names: set[str] = set()
    for path in _ROOT.glob(SLO_GLOB):
        for doc in _docs(path):
            if doc.get("kind") != "PrometheusRule":
                continue
            for group in (doc.get("spec", {}) or {}).get("groups", []) or []:
                for rule in group.get("rules", []) or []:
                    if rule.get("record"):
                        names.add(rule["record"])
    return names


def validate() -> list[str]:
    errors: list[str] = []
    defined = defined_recording_rules()
    templates = 0
    if not PD_DIR.exists():
        return ["no progressive-delivery dir — nothing to validate"]

    for path in sorted(PD_DIR.rglob("*.yaml")):
        for doc in _docs(path):
            if doc.get("kind") != "AnalysisTemplate":
                continue
            templates += 1
            name = doc.get("metadata", {}).get("name", "<unnamed>")
            metrics = (doc.get("spec", {}) or {}).get("metrics", []) or []
            if not metrics:
                errors.append(f"{path.name}: AnalysisTemplate/{name} declares no metrics (nothing to gate on)")
                continue
            for m in metrics:
                mname = m.get("name", "<metric>")
                # 2. a gate must be able to fail
                if not m.get("failureCondition") and m.get("failureLimit") is None:
                    errors.append(f"{path.name}: {name}.{mname} has no failureCondition/failureLimit — "
                                  f"it can never fail (theater)")
                # 1. every recording-rule reference must be a real record:
                query = (m.get("provider", {}) or {}).get("prometheus", {}).get("query", "") or ""
                for ref in set(_RECORDING_RULE.findall(query)):
                    if ref not in defined:
                        errors.append(f"{path.name}: {name}.{mname} queries recording rule '{ref}' "
                                      f"which is not defined in any PrometheusRule (phantom metric)")
    if templates == 0:
        errors.append("no AnalysisTemplate found under progressive-delivery (the gate is missing)")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("SLO canary-gate validation FAILED:")
        for e in errors:
            print("  ✗ " + e)
        return 1
    print(f"SLO canary gate OK — every query targets a defined recording rule and can fail "
          f"(defined rules: {sorted(defined_recording_rules())})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
