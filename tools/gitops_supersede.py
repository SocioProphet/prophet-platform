#!/usr/bin/env python3
"""Genetic-superset selection for gitops-promote PRs.

Pure, deterministic, no-network logic. gitops-promote opens one values-only PR per
built commit, re-pinning the CHANGED services to the fresh image sha. When a service
is rebuilt again before its earlier promote PR merges, the earlier PR is strictly
DOMINATED — every values file it touches is re-pinned (to a newer sha) by the newer
PR. Keeping it open wastes the self-hosted runner pool and lands a stale pin if merged
out of order.

This module decides which OPEN promote PRs a newer promote PR supersedes:

    a promote PR P is superseded by the new PR N iff
      * P touches at least one file, and
      * every file P touches is also touched by N        (files(P) ⊆ files(N)), and
      * P and N are both values-only promotes            (all files under deploy/values/).

Equal filesets are dominated too (same services, newer sha wins) — N is by construction
the newest, so an older equal-set promote is closed in favour of it: "newest-per-service".

The workflow feeds live PR/file data in on stdin and CLOSES the returned PRs; the
domination rule itself lives here so it is unit-tested and cannot regress silently.
"""

from __future__ import annotations

import json
import sys
from typing import Iterable

VALUES_PREFIX = "deploy/values/"


def _is_values_only(files: Iterable[str]) -> bool:
    files = list(files)
    return bool(files) and all(f.startswith(VALUES_PREFIX) for f in files)


def superseded_prs(new_files: Iterable[str], others: Iterable[dict]) -> dict:
    """Return {'superseded': [numbers], 'kept': [numbers]} — deterministic, sorted.

    new_files : the values files the NEW promote PR changes.
    others    : [{'number': int, 'files': [str, ...]}, ...] — the other OPEN promote PRs.
    """
    new_set = set(new_files)
    new_is_values_only = _is_values_only(new_set)
    superseded: list[int] = []
    kept: list[int] = []
    for pr in others:
        number = pr["number"]
        pr_files = set(pr.get("files") or [])
        dominated = (
            new_is_values_only
            and _is_values_only(pr_files)
            and pr_files  # non-empty
            and pr_files <= new_set  # every file also re-pinned by the newer PR
        )
        (superseded if dominated else kept).append(number)
    return {"superseded": sorted(superseded), "kept": sorted(kept)}


def main(argv: list[str] | None = None) -> int:
    """Read {'new_files': [...], 'others': [...]} from stdin; write the verdict to stdout."""
    payload = json.load(sys.stdin)
    verdict = superseded_prs(payload["new_files"], payload.get("others", []))
    json.dump(verdict, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
