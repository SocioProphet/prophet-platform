"""Teeth for the canary SLO-gate check.

A gate that has only ever passed proves nothing. These exercise
tools/check_canary_slo_gate.py against a POSITIVE (fail-closed) and a NEGATIVE
(failureCondition-only, the shape the estate actually shipped) fixture, and assert
the real shipped AnalysisTemplate is itself fail-closed.
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_canary_slo_gate as chk  # noqa: E402

FAIL_CLOSED = textwrap.dedent(
    """
    apiVersion: argoproj.io/v1alpha1
    kind: AnalysisTemplate
    metadata:
      name: good-gate
    spec:
      metrics:
        - name: error-ratio
          successCondition: len(result) > 0 && result[0] < 0.05
          failureCondition: len(result) == 0 || result[0] >= 0.05
          failureLimit: 1
    """
)

# The pre-remediation shape: only a failureCondition. On an empty series the
# threshold is never met, so Argo Rollouts scores the step Successful and promotes.
FAILURE_ONLY = textwrap.dedent(
    """
    apiVersion: argoproj.io/v1alpha1
    kind: AnalysisTemplate
    metadata:
      name: bad-gate
    spec:
      metrics:
        - name: error-ratio
          failureCondition: result[0] >= 0.05
          failureLimit: 1
    """
)


def test_fail_closed_template_passes():
    assert chk.scan_text(FAIL_CLOSED, "good.yaml") == []


def test_failure_only_template_is_rejected():
    violations = chk.scan_text(FAILURE_ONLY, "bad.yaml")
    assert violations, "a failureCondition-only SLO gate must be rejected (no-data promotes)"
    joined = "\n".join(violations)
    assert "data-presence guard" in joined
    assert "does not fail on absent data" in joined


def test_missing_absence_clause_alone_is_rejected():
    # Has a presence guard in successCondition but the failureCondition still lets
    # an empty series through — must still be flagged.
    doc = textwrap.dedent(
        """
        apiVersion: argoproj.io/v1alpha1
        kind: AnalysisTemplate
        metadata: { name: half-gate }
        spec:
          metrics:
            - name: m
              successCondition: len(result) > 0 && result[0] < 0.05
              failureCondition: result[0] >= 0.05
        """
    )
    violations = chk.scan_text(doc, "half.yaml")
    assert any("absent data" in v for v in violations)


def test_shipped_slo_gate_is_fail_closed():
    # The AnalysisTemplate this PR ships must itself pass the check on real data.
    root = Path(chk.ROOT)
    assert chk.scan_repo(root) == [], "shipped AnalysisTemplates must be fail-closed on no-data"
