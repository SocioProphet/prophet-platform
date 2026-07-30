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

TRUST: the workflow reads THIS FILE FROM THE BASE REF, not from the PR checkout. Running
the PR's own copy would let a pull request edit this detector to answer "true"
unconditionally and thereby skip app-test and smoke for its entire diff — a detector
certifying its own modification. See the `changes` job in
.github/workflows/validate-target-diagnostics.yml and the structural test that pins it.
"""
from __future__ import annotations

import posixpath
import re
import sys

# Extensions that are genuinely inert to application and service tests: prose and images.
# NOT "anything under docs/" — a docs directory can legally hold executable and
# machine-consumed files (docs/conf.py, docs/scripts/gen.ts), and this repo already carries
# docs/design-register.yaml, which a workflow reads, plus docs/generated/**/*.json schema
# examples. Treating those as inert is a coverage hole that opens itself the day someone
# adds the file. An allowlist fails in the safe direction: an extension not named here
# runs everything.
DOC_SUFFIXES = frozenset({
    '.md', '.rst', '.txt',
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.pdf',
})

# A top-level markdown file (README.md, CHANGELOG.md). Anchored and slash-explicit so
# `apps/svc/README.md`, which sits beside code, does NOT match.
TOP_LEVEL_MD = re.compile(r'^[^/]+\.md$')


def _inert(path: str) -> bool:
    """One path's verdict. An unrecognised shape is never inert."""
    if TOP_LEVEL_MD.match(path):
        return True
    # Slash-explicit so `docsomething/x.py` is not read as a docs path.
    if not path.startswith('docs/'):
        return False
    return posixpath.splitext(path)[1].lower() in DOC_SUFFIXES


def docs_only(paths: list[str]) -> bool:
    cleaned = [p.strip() for p in paths if p.strip()]
    if not cleaned:
        return False  # an empty diff tells us nothing; run everything
    return all(_inert(p) for p in cleaned)


def main() -> int:
    print('true' if docs_only(sys.stdin.read().splitlines()) else 'false')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
