#!/usr/bin/env python3
"""Enforce that every Argo Rollouts AnalysisTemplate metric is FAIL-CLOSED on no data.

A canary SLO metric that declares only ``failureCondition: result[0] >= X`` treats an
EMPTY Prometheus result — a service that does not export the queried recording rule — as
"not a failure": the step scores Successful and the rollout promotes a release that nothing
measured. Prometheus "no data" is not the same as "healthy". The estate shipped exactly this
shape (slo-gate, wired to hellgraph-service, which exports no metrics), so an unguarded gate
would let a broken canary graduate.

This check requires, for every metric whose success/failure condition thresholds on
``result[...]``, BOTH:

  * a successCondition that requires the series to EXIST   — ``len(result) > 0`` (or ``>= 1``), and
  * a failureCondition that fires when the series is ABSENT — ``len(result) == 0`` (or ``< 1``),

so that a missing series ABORTS the canary instead of promoting it.

Runs in the validate-target-diagnostics gate (``make canary-slo-gate-check``). It is proven
able to go red by tools/tests/test_check_canary_slo_gate.py, which feeds it a positive
(fail-closed) and a negative (failureCondition-only) fixture — a gate that has only ever
passed proves nothing.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Iterable

import yaml

ROOT = Path(__file__).resolve().parents[1]

ANALYSIS_KINDS = {"AnalysisTemplate", "ClusterAnalysisTemplate"}

# A metric is subject to the no-data trap when any of its conditions threshold on result[...].
_RESULT_REF = re.compile(r"\bresult\s*\[")
# Data-presence guard accepted forms: len(result) > 0  |  len(result) >= 1
_PRESENCE = re.compile(r"len\s*\(\s*result\s*\)\s*(?:>\s*0|>=\s*1)")
# Absent-data clause accepted forms: len(result) == 0  |  len(result) < 1  |  len(result) <= 0
_ABSENCE = re.compile(r"len\s*\(\s*result\s*\)\s*(?:==\s*0|<\s*1|<=\s*0)")


def _iter_docs(text: str) -> Iterable[dict[str, Any]]:
    try:
        docs = yaml.safe_load_all(text)
        for doc in docs:
            if isinstance(doc, dict):
                yield doc
    except yaml.YAMLError:
        return


def metric_violations(metric: dict[str, Any], where: str) -> list[str]:
    name = metric.get("name", "<unnamed>")
    succ = str(metric.get("successCondition", "") or "")
    fail = str(metric.get("failureCondition", "") or "")
    # Only metrics that threshold on a result value can silently pass on an empty series.
    if not (_RESULT_REF.search(succ) or _RESULT_REF.search(fail)):
        return []
    out: list[str] = []
    if not _PRESENCE.search(succ):
        out.append(
            f"{where}: metric '{name}' has no data-presence guard — add a successCondition "
            f"requiring len(result) > 0 so an empty series is not scored as healthy "
            f"(successCondition={succ!r})"
        )
    if not _ABSENCE.search(fail):
        out.append(
            f"{where}: metric '{name}' does not fail on absent data — add len(result) == 0 to "
            f"the failureCondition so a missing series ABORTS the canary "
            f"(failureCondition={fail!r})"
        )
    return out


def template_violations(doc: dict[str, Any], where: str) -> list[str]:
    md_name = (doc.get("metadata") or {}).get("name", "?")
    metrics = ((doc.get("spec") or {}).get("metrics")) or []
    out: list[str] = []
    if not metrics:
        out.append(f"{where}: AnalysisTemplate '{md_name}' declares no metrics")
        return out
    for m in metrics:
        if isinstance(m, dict):
            out.extend(metric_violations(m, where))
    return out


def scan_text(text: str, where: str) -> list[str]:
    out: list[str] = []
    for doc in _iter_docs(text):
        if doc.get("kind") in ANALYSIS_KINDS:
            out.extend(template_violations(doc, where))
    return out


def scan_repo(root: Path) -> list[str]:
    out: list[str] = []
    for path in sorted(root.rglob("*.y*ml")):
        s = str(path)
        if "/node_modules/" in s or "/vendor/" in s or "/.git/" in s:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        # Cheap prefilter — the kind check inside scan_text is authoritative.
        if "AnalysisTemplate" not in text:
            continue
        out.extend(scan_text(text, str(path.relative_to(root))))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Enforce fail-closed Argo Rollouts SLO gates")
    ap.add_argument("--root", default=str(ROOT), type=Path, help="repo root to scan")
    args = ap.parse_args(argv)
    violations = scan_repo(Path(args.root))
    if violations:
        print("canary-slo-gate-check: FAIL — SLO AnalysisTemplate(s) are not fail-closed on no-data:")
        for v in violations:
            print(f"  - {v}")
        print(
            "\nWhy: an empty Prometheus series must ABORT a canary, not promote it "
            "('no data' != 'healthy'). See infra/k8s/rollouts/base/analysistemplate-slo.yaml."
        )
        return 1
    print("canary-slo-gate-check: OK — every AnalysisTemplate metric fails closed on absent data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
