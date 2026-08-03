#!/usr/bin/env python3
"""Contract tooth: gitops-promote must publish BOTH required contexts, fail-closed.

The whole self-completing-promote fix is: a bot-authored promote PR can never get its
required checks from an event-triggered run (GITHUB_TOKEN no-recursion), so gitops-promote
publishes them itself as commit statuses. main requires TWO contexts:
  * `diagnostics-gate` — the main-required-checks ruleset
  * `gate / check`     — classic branch protection (app_id 15368)
Publishing only the first is exactly the bug that left promote PRs BLOCKED at
mergeStateStatus=UNKNOWN until a human admin-merged them. This test parses the workflow
and asserts both contexts are posted, that a `pending` is posted before any `success`
(fail-closed by construction), and that the genetic-superset self-selection is wired in.

Run: python3 -m pytest -q tools/tests/test_gitops_promote_gate_contract.py
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "gitops-promote.yml"


def _promote_run_script() -> str:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = doc["jobs"]["promote"]["steps"]
    return "\n".join(s.get("run", "") for s in steps)


def test_both_required_contexts_are_published() -> None:
    script = _promote_run_script()
    assert "diagnostics-gate" in script, "the ruleset context must still be published"
    assert "gate / check" in script, (
        "classic branch protection requires the `gate / check` context; without it a "
        "promote PR sits at mergeStateStatus=UNKNOWN and never auto-merges"
    )


def test_pending_is_published_before_success() -> None:
    script = _promote_run_script()
    # Fail-closed: the required checks must be driven to `pending` first, so a job that
    # dies mid-flight leaves the PR visibly blocked, not invisibly absent.
    assert "post_status pending" in script
    first_pending = script.index("post_status pending")
    first_success = script.index("post_status success")
    assert first_pending < first_success, "must post pending before success (fail-closed)"


def test_success_is_the_only_certifying_state() -> None:
    script = _promote_run_script()
    # The certifying line only runs after the fail-closed per-job allowlist check.
    assert "post_status success" in script
    assert 'select(.conclusion != "success")' in script, (
        "verdict must be an allowlist on `success`, never a denylist of known-bad states"
    )


def test_genetic_superset_selfselection_is_wired() -> None:
    script = _promote_run_script()
    assert "gitops_supersede.py" in script, (
        "newer promotes must auto-close dominated (superseded) promote PRs"
    )


def test_statuses_write_permission_declared() -> None:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    perms = doc["jobs"]["promote"].get("permissions") or doc.get("permissions") or {}
    assert perms.get("statuses") == "write", (
        "posting commit statuses for both required contexts needs statuses: write"
    )


if __name__ == "__main__":
    import subprocess

    raise SystemExit(subprocess.call(["python3", "-m", "pytest", "-q", __file__]))
