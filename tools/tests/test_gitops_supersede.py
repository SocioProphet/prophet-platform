#!/usr/bin/env python3
"""Teeth for gitops-promote's genetic-superset self-selection.

A self-selection rule that has never been shown to CLOSE a dominated promote, nor to
KEEP an independent one, is as suspect as an unenforced rule. superseded_prs is pure,
so we drive it directly and assert both directions. Deterministic, no network.

Run: python3 -m pytest -q tools/tests/test_gitops_supersede.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gitops_supersede as gs  # noqa: E402


def test_equal_fileset_is_superseded_newest_per_service() -> None:
    # Same service re-pinned to a newer sha: the older promote PR is dominated.
    out = gs.superseded_prs(
        ["deploy/values/hellgraph-service.yaml"],
        [{"number": 1301, "files": ["deploy/values/hellgraph-service.yaml"]}],
    )
    assert out == {"superseded": [1301], "kept": []}


def test_strict_subset_is_superseded() -> None:
    # New PR re-pins A and B; an older PR that only touched A is dominated.
    out = gs.superseded_prs(
        ["deploy/values/a.yaml", "deploy/values/b.yaml"],
        [{"number": 10, "files": ["deploy/values/a.yaml"]}],
    )
    assert out["superseded"] == [10] and out["kept"] == []


def test_independent_service_is_kept() -> None:
    # Older PR touches C, which the new PR does not re-pin -> NOT dominated, keep it.
    out = gs.superseded_prs(
        ["deploy/values/a.yaml"],
        [{"number": 20, "files": ["deploy/values/c.yaml"]}],
    )
    assert out == {"superseded": [], "kept": [20]}


def test_superset_pr_is_kept() -> None:
    # Older PR touches A and B; new PR only re-pins A -> older is NOT a subset, keep it.
    out = gs.superseded_prs(
        ["deploy/values/a.yaml"],
        [{"number": 30, "files": ["deploy/values/a.yaml", "deploy/values/b.yaml"]}],
    )
    assert out == {"superseded": [], "kept": [30]}


def test_empty_pr_is_never_closed() -> None:
    # A PR with no recorded files must never be auto-closed (fail-safe).
    out = gs.superseded_prs(
        ["deploy/values/a.yaml"],
        [{"number": 40, "files": []}],
    )
    assert out == {"superseded": [], "kept": [40]}


def test_non_values_new_pr_closes_nothing() -> None:
    # If the "new" change is not a pure values promote, refuse to close anything.
    out = gs.superseded_prs(
        ["deploy/values/a.yaml", "services/a/main.go"],
        [{"number": 50, "files": ["deploy/values/a.yaml"]}],
    )
    assert out == {"superseded": [], "kept": [50]}


def test_non_values_candidate_is_kept() -> None:
    # A candidate PR touching source (not a pure values promote) is never auto-closed.
    out = gs.superseded_prs(
        ["deploy/values/a.yaml"],
        [{"number": 60, "files": ["deploy/values/a.yaml", "services/a/main.go"]}],
    )
    assert out == {"superseded": [], "kept": [60]}


def test_mixed_batch_is_deterministic_and_sorted() -> None:
    out = gs.superseded_prs(
        ["deploy/values/a.yaml", "deploy/values/b.yaml"],
        [
            {"number": 3, "files": ["deploy/values/b.yaml"]},
            {"number": 1, "files": ["deploy/values/a.yaml"]},
            {"number": 2, "files": ["deploy/values/z.yaml"]},
        ],
    )
    assert out == {"superseded": [1, 3], "kept": [2]}


if __name__ == "__main__":
    import subprocess

    raise SystemExit(subprocess.call(["python3", "-m", "pytest", "-q", __file__]))
