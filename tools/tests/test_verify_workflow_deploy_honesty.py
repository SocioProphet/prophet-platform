"""Prove INV-DEPLOY-HONESTY (the deploy-honesty gate) fires in both directions.

A gate that never denies proves nothing. These tests exercise the pure
`scan()` and `evaluate()` classifiers against synthetic workflow YAML and
synthetic hit lists — no filesystem side-effects outside a tempdir, no network.

Critical negative case (the one that earns gate registration):
  * A workflow line with `kubectl apply ... || true` → DISHONEST detected.

Additional cases:
  * Honest apply (no swallow) → clean.
  * Helm upgrade swallowed → DISHONEST detected.
  * `kubectl get ... || true` (informational, not a mutation) → clean.
  * STALE allowlist entry (known violation absent from scan) → STALE detected.
  * Known-broken entry that still appears → NOT re-flagged as new.
  * Empty workflow dir → clean.
  * Multiple violations in one file → all reported.
"""
from __future__ import annotations

import importlib.util
import sys
import textwrap
import tempfile
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "verify_workflow_deploy_honesty.py"
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("verify_workflow_deploy_honesty", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)

scan     = MOD.scan
evaluate = MOD.evaluate
KNOWN_BROKEN = MOD.KNOWN_BROKEN


def _workflow_dir(yaml_content: str):
    """Context manager: tempdir with a single deploy.yml containing yaml_content."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "deploy.yml"
            p.write_text(textwrap.dedent(yaml_content))
            yield Path(d)

    return _ctx()


# ── NEGATIVE cases (prove the gate can fire) ──────────────────────────────────

def test_swallowed_kubectl_apply_detected():
    """kubectl apply ... || true — the canonical dishonest-deploy pattern."""
    with _workflow_dir("run: kubectl apply -f manifests/ || true\n") as d:
        hits = scan(d)
    assert len(hits) == 1, f"expected 1 hit, got {hits}"
    assert "deploy.yml" in hits[0]

    problems = evaluate(hits, frozenset())
    assert len(problems) == 1
    assert "DISHONEST" in problems[0]


def test_swallowed_helm_upgrade_detected():
    """helm upgrade --install ... || : — shell no-op is equally dishonest."""
    with _workflow_dir("run: helm upgrade --install myapp ./chart || :\n") as d:
        hits = scan(d)
    assert len(hits) == 1
    problems = evaluate(hits, frozenset())
    assert any("DISHONEST" in p for p in problems)


def test_swallowed_kubectl_delete_detected():
    """kubectl delete is a mutation — swallowing its failure is dishonest."""
    with _workflow_dir("run: kubectl delete -f stale.yml || true\n") as d:
        hits = scan(d)
    assert len(hits) >= 1
    problems = evaluate(hits, frozenset())
    assert any("DISHONEST" in p for p in problems)


def test_multiple_violations_all_reported():
    """Multiple dishonest lines in one file — no short-circuit on the first."""
    yaml = (
        "run: kubectl apply -f a.yaml || true\n"
        "run: kubectl create -f b.yaml || true\n"
        "run: helm upgrade --install c ./chart || :\n"
    )
    with _workflow_dir(yaml) as d:
        hits = scan(d)
    assert len(hits) == 3
    problems = evaluate(hits, frozenset())
    assert len(problems) == 3


def test_stale_allowlist_entry_flagged():
    """A KNOWN_BROKEN entry that is absent from the scan is a STALE ratchet entry."""
    stale_key = "deploy.yml::kubectl apply -f old.yaml || true"
    problems = evaluate([], frozenset({stale_key}))
    assert len(problems) == 1
    assert "STALE" in problems[0]
    assert "deploy.yml" in problems[0]


# ── POSITIVE cases (gate must NOT fire spuriously) ────────────────────────────

def test_honest_apply_clean():
    """kubectl apply without a swallow is fine."""
    yaml = (
        "run: kubectl apply -f manifests/\n"
        "run: kubectl rollout status deploy/x --timeout=60s\n"
    )
    with _workflow_dir(yaml) as d:
        hits = scan(d)
    assert hits == []


def test_informational_get_or_true_not_flagged():
    """`kubectl get ... || true` is a read, not a mutation — must not be flagged."""
    with _workflow_dir("run: kubectl get pods || true\n") as d:
        hits = scan(d)
    assert hits == [], f"unexpected hit on informational get: {hits}"


def test_empty_workflow_dir_clean():
    """No workflows → clean."""
    with tempfile.TemporaryDirectory() as d:
        hits = scan(Path(d))
    assert hits == []


def test_known_broken_entry_not_re_flagged():
    """A violation already in KNOWN_BROKEN must not be flagged again as a new problem."""
    hit_line = "deploy.yml:1: kubectl apply -f m.yaml || true"
    # Build the same key format the tool uses
    key = hit_line.split(":", 2)[0] + "::" + hit_line.split(": ", 1)[-1]
    problems = evaluate([hit_line], frozenset({key}))
    assert not any("DISHONEST" in p for p in problems), f"re-flagged a known entry: {problems}"


def test_real_estate_workflows_clean():
    """The live .github/workflows/ directory must be clean (zero KNOWN_BROKEN today)."""
    import os
    repo_root = Path(__file__).resolve().parents[3]
    wf_dir = repo_root / ".github" / "workflows"
    if not wf_dir.is_dir():
        return   # not run from repo root — skip rather than false-fail
    hits = scan(wf_dir)
    problems = evaluate(hits, KNOWN_BROKEN)
    assert problems == [], f"live workflows have dishonest-deploy problems:\n" + "\n".join(problems)
