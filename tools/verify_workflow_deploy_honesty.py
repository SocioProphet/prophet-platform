#!/usr/bin/env python3
"""Workflow deploy-honesty gate — generalizes the 2026-08-04 orphan-gitea lesson.

The gitea git server crashlooped 26h because a deploy workflow reported GREEN while a workload it
applied was broken: it swallowed the outcome with `|| true`. A deploy control that does not let a
failure fail is a paper control. This gate refuses the clearest form of that anti-pattern across
`.github/workflows/`:

  a cluster MUTATION whose own failure is SWALLOWED — `kubectl apply|create|replace|patch|delete|
  scale … || true` (or `|| :`), or `helm install|upgrade … || true`.

You may never swallow a mutation's exit in a deploy step: if the apply/upgrade fails, the step
must fail. (Informational reads are out of scope; the "verify EVERYTHING you apply" half is
enforced at runtime by the orphan detector + the per-deploy rollout checks.)

Shrink-only ratchet (like the moving-tag / sovereignty gates): a NEW swallowed-mutation fails the
build; a KNOWN_BROKEN entry that no longer appears must be deleted. Self-excluding (this is a tool,
not a workflow); teeth proven by an inline self-test. Static — safe for hermetic `make validate`.

  verify_workflow_deploy_honesty.py            # scan .github/workflows
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"

# A cluster mutation ...
_MUTATION = r"(kubectl\s+(apply|create|replace|patch|delete|scale|rollout\s+restart)\b|helm\s+(install|upgrade)\b)"
# ... whose failure is swallowed on the same line. `(?![\w-])` matches a bare `:` (shell no-op)
# at end/space as well as `true`, without matching `trueish`.
_SWALLOW = r"\|\|\s*(true|:)(?![\w-])"
_DISHONEST = re.compile(_MUTATION + r"[^\n]*?" + _SWALLOW)

# Shrink-only allowlist: "<file>:<lineno-independent stable substring>" of existing violations.
# Empty today — the estate is clean on this pattern. Do not add; a new one is meant to fail.
KNOWN_BROKEN: frozenset[str] = frozenset()


def scan(workflow_dir: Path) -> list[str]:
    """Return 'file: line' for every swallowed-mutation found."""
    hits: list[str] = []
    if not workflow_dir.is_dir():
        return hits
    for path in sorted(workflow_dir.glob("*.y*ml")):
        try:
            for i, line in enumerate(path.read_text().splitlines(), 1):
                if _DISHONEST.search(line):
                    hits.append(f"{path.name}:{i}: {line.strip()[:120]}")
        except OSError:
            continue
    return hits


def evaluate(hits: list[str], known: frozenset[str]) -> list[str]:
    problems: list[str] = []
    hit_keys = {h.split(":", 2)[0] + "::" + h.split(": ", 1)[-1] for h in hits}
    for h in hits:
        key = h.split(":", 2)[0] + "::" + h.split(": ", 1)[-1]
        if key not in known:
            problems.append(f"DISHONEST deploy (mutation whose failure is swallowed): {h}")
    for k in sorted(known):
        if k not in hit_keys:
            problems.append(f"STALE allowlist entry no longer present: {k} — remove it (ratchet shrinks)")
    return problems


def _self_test() -> bool:
    good = 'kubectl apply -f m.yaml\nkubectl rollout status deploy/x --timeout=60s'
    bad1 = 'kubectl apply -f m.yaml || true'
    bad2 = 'helm upgrade --install x ./chart || :'
    ok_get = 'kubectl get pods || true    # informational read — out of scope'
    checks = [
        ("swallowed apply is caught", bool(_DISHONEST.search(bad1))),
        ("swallowed helm upgrade is caught", bool(_DISHONEST.search(bad2))),
        ("honest apply+verify passes", not _DISHONEST.search(good)),
        ("informational get||true not flagged", not _DISHONEST.search(ok_get)),
        ("new violation fails the gate", evaluate(["w.yml:1: kubectl apply -f m || true"], frozenset()) != []),
    ]
    ok = all(v for _, v in checks)
    for name, v in checks:
        print(f"    {'OK  ' if v else 'FAIL'} self-test: {name}")
    return ok


def main() -> int:
    if not _self_test():
        print("FAIL: self-test did not pass — the workflow-honesty gate has no teeth")
        return 2
    hits = scan(WORKFLOW_DIR)
    problems = evaluate(hits, KNOWN_BROKEN)
    if problems:
        print(f"FAIL: {len(problems)} workflow deploy-honesty problem(s):")
        for p in problems:
            print(f"  {p}")
        return 1
    print(f"OK: no deploy workflow swallows a mutation's failure ({len(hits)} swallowed-mutations, "
          f"{len(KNOWN_BROKEN)} allowlisted)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
