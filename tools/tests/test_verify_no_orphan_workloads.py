"""Prove INV-ORPHAN (the orphan-workload detector) fires in both directions.

A gate that never denies proves nothing. These tests exercise the pure
`find_problems()` classifier against synthetic deployment lists — no kubectl,
no cluster, no network.

Critical negative case (the one that earns gate registration):
  * A deployment with no ArgoCD/Helm labels that is NOT in the allowlist → ORPHAN detected.

Additional cases:
  * A deployment managed by ArgoCD → clean.
  * A deployment managed by Helm → clean.
  * A deployment in the allowlist but out-of-band → sanctioned, not an orphan.
  * An allowlist entry that is now ArgoCD-managed → STALE entry detected (ratchet shrinks).
  * Multiple orphans → all reported, no short-circuit.
  * An empty deployment list → clean (no false positives on an empty cluster).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "verify_no_orphan_workloads.py"
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("verify_no_orphan_workloads", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)

find_problems = MOD.find_problems
SANCTIONED = MOD.SANCTIONED_OUT_OF_BAND


def _deploy(name: str, *, argocd: bool = False, helm: bool = False) -> dict:
    """Build a minimal synthetic Deployment dict."""
    annotations: dict = {}
    labels: dict = {}
    if argocd:
        annotations["argocd.argoproj.io/tracking-id"] = "app:ns:kind/name"
        labels["argocd.argoproj.io/instance"] = "app"
    if helm:
        labels["app.kubernetes.io/managed-by"] = "Helm"
    return {"metadata": {"name": name, "annotations": annotations, "labels": labels}}


# ── NEGATIVE case (proves the gate can fire) ──────────────────────────────────

def test_orphan_workload_detected():
    """An out-of-band workload NOT in the allowlist is flagged — the gate must fire."""
    problems = find_problems([_deploy("rogue-service")], allowlist=frozenset())
    assert len(problems) == 1
    assert "ORPHAN" in problems[0]
    assert "rogue-service" in problems[0]


def test_orphan_workload_not_in_sanctioned_allowlist():
    """The gate still fires even when SANCTIONED_OUT_OF_BAND is the real list."""
    problems = find_problems([_deploy("rogue-service")], allowlist=SANCTIONED)
    assert any("rogue-service" in p for p in problems)


def test_multiple_orphans_all_reported():
    """Multiple orphans are all reported — no short-circuit on the first."""
    problems = find_problems(
        [_deploy("alpha"), _deploy("beta"), _deploy("gamma")],
        allowlist=frozenset(),
    )
    assert len(problems) == 3
    names = [p for p in problems if "ORPHAN" in p]
    assert len(names) == 3


# ── POSITIVE cases (gate must NOT fire spuriously) ────────────────────────────

def test_argocd_managed_clean():
    problems = find_problems([_deploy("my-app", argocd=True)], allowlist=frozenset())
    assert problems == []


def test_helm_managed_clean():
    problems = find_problems([_deploy("my-chart", helm=True)], allowlist=frozenset())
    assert problems == []


def test_sanctioned_out_of_band_allowed():
    """A deployment on the allowlist is NOT flagged even though it's out-of-band."""
    problems = find_problems([_deploy("gitea")], allowlist=frozenset({"gitea"}))
    assert problems == []


def test_empty_cluster_clean():
    problems = find_problems([], allowlist=frozenset())
    assert problems == []


# ── STALE allowlist detection ─────────────────────────────────────────────────

def test_stale_allowlist_entry_detected():
    """If a workload in the allowlist is now ArgoCD-managed, that's a stale entry."""
    problems = find_problems(
        [_deploy("gitea", argocd=True)],
        allowlist=frozenset({"gitea"}),
    )
    assert len(problems) == 1
    assert "STALE" in problems[0]
    assert "gitea" in problems[0]


def test_allowlist_entry_absent_from_cluster_is_clean():
    """An allowlisted workload that doesn't exist on the cluster is not a problem."""
    problems = find_problems(
        [_deploy("other-app", argocd=True)],
        allowlist=frozenset({"gitea"}),   # gitea not present
    )
    assert problems == []


# ── Mixed scenario ────────────────────────────────────────────────────────────

def test_mixed_managed_orphan_sanctioned():
    """Clean+orphan+sanctioned in one pass: only the orphan shows up."""
    deployments = [
        _deploy("legitimate", argocd=True),   # clean
        _deploy("rogue-service"),              # orphan
        _deploy("gitea"),                      # sanctioned
    ]
    problems = find_problems(deployments, allowlist=frozenset({"gitea"}))
    assert len(problems) == 1
    assert "rogue-service" in problems[0]
