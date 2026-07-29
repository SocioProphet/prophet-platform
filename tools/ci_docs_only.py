#!/usr/bin/env python3
"""Decide whether a diff is provably inert for app-code and service-behaviour tests.

Extracted from the workflow on purpose: a skip rule embedded in YAML is a skip rule nobody
can test, and a CI optimisation that silently stops running tests is worse than no
optimisation at all. This is the code the workflow calls, so tools/tests exercises exactly
what production executes — no second copy to drift.

CONTRACT
  stdin  : newline-separated changed paths (as `git diff --name-only` emits them)
  stdout : "true" if the app-test/smoke legs may skip, else "false"

SAFETY: the answer is "false" (run everything) unless every single path is on the inert
allowlist. Empty input, unrecognised paths, mixed diffs — all run everything. Skipping
requires positive proof of inertness, never absence of evidence.

SCOPE: "inert" here means inert *to application and service tests*. It does NOT mean
unvalidated — the validate-target-diagnostics legs (including validate-repo, which asserts
REQUIRED_FILES such as docs/ARCHITECTURE.md and scans for TODO/PLACEHOLDER) are never
skipped, so documentation keeps its own coverage.
"""
from __future__ import annotations

import re
import sys

# A path is inert only if it is inside docs/ or is a top-level markdown file.
# Anchored and slash-explicit so `docsomething/x.py` and `apps/svc/README.md` do NOT match.
INERT = re.compile(r'^(docs/|[^/]+\.md$)')


def docs_only(paths: list[str]) -> bool:
    cleaned = [p.strip() for p in paths if p.strip()]
    if not cleaned:
        return False  # an empty diff tells us nothing; run everything
    return all(INERT.match(p) for p in cleaned)


def main() -> int:
    print('true' if docs_only(sys.stdin.read().splitlines()) else 'false')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
