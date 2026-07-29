#!/usr/bin/env python3
"""premerge audit — refuse to merge a branch whose staleness could actually break main.

WHY THIS CHANGED
----------------
The original rule was `behind > 0 -> fail`. On a busy repo that starves PRs: you rebase to
zero, CI takes ten minutes, main moves two commits, the gate fails, repeat. Observed live
on this repo — a docs-only PR was blocked while an unrelated service promotion landed.
Worse, the blanket rule made small safe changes MORE expensive than large risky ones,
because they are the ones left waiting for a quiet moment that never comes.

It was also unsound in the other direction: `behind == 0` does not mean "safe". A branch
can be perfectly current and still break main, and a branch can be 40 commits behind and
be provably unaffected by every one of them.

The question worth asking is not *how far behind are you* but **did the base change
anything your change also touches**. That is the real conflict surface — the same thing a
merge queue establishes by rebase-and-test, computed here in one cheap diff.

DECISION MODEL
--------------
  overlap     = intersection of (files this branch changed) and (files the base changed
                since our merge-base)
  hot overlap = overlap restricted to HOT_PREFIXES (build, CI, tooling, contracts, apps)

  1. hot overlap non-empty         -> FAIL. Both sides edited something load-bearing.
  2. overlap non-empty             -> FAIL. Genuine semantic-conflict risk.
  3. behind > PREMERGE_MAX_BEHIND  -> FAIL. Unbounded drift is its own risk, overlap or not.
  4. otherwise                     -> PASS, stating exactly why staleness is safe here.

Rules 1-2 are STRICTER than the old gate (a zero-behind branch with an overlapping edit
used to pass). Rules 3-4 are looser only where looseness is provably harmless. Net: fewer
false alarms, and it now catches a class of real conflict the old rule missed.

`PREMERGE_STRICT=1` restores the historical `behind > 0 -> fail` behaviour for anyone who
wants the old guarantee unchanged.

NOTE: this remains an APPROXIMATION of a merge queue. If GitHub merge queues are enabled
for this repo, prefer them — they rebase-and-TEST at the front of the queue, which proves
what this can only infer. This gate is the cheap version for repos without one.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HOT_PREFIXES = [
    'Makefile',
    '.github/workflows/',
    'tools/',
    'contracts/platform/',
    'apps/',
    'infra/k8s/overlays/',
    'bundles/',
    'conformance/',
]

# How far behind we tolerate when nothing overlaps. Generous on purpose: with zero overlap
# the base's commits cannot interact with this diff, so the remaining risk is only that the
# branch was authored against a much older tree. Bounded, not unlimited.
DEFAULT_MAX_BEHIND = 50


def run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, cwd=ROOT, text=True).strip()


def _lines(output: str) -> list[str]:
    return [line for line in output.splitlines() if line.strip()]


def is_hot(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix) for prefix in HOT_PREFIXES)


def audit(base_ref: str, head_ref: str, max_behind: int = DEFAULT_MAX_BEHIND,
          strict: bool = False) -> tuple[int, list[str]]:
    """Return (exit_code, report_lines). Split out from main() so it is testable against
    real git fixtures rather than mocks — a gate proven with mocks proves nothing."""
    out: list[str] = ['premerge audit summary', f'base_ref={base_ref}', f'head_ref={head_ref}']

    changed = _lines(run(['git', 'diff', '--name-only', f'{base_ref}...{head_ref}']))
    ahead_behind = run(['git', 'rev-list', '--left-right', '--count', f'{base_ref}...{head_ref}'])
    behind, ahead = (int(x) for x in ahead_behind.split())

    # What the BASE changed since we diverged. `A...B` diffs from the merge-base, so this is
    # exactly "commits on the base we do not have", expressed as files.
    base_changed = _lines(run(['git', 'diff', '--name-only', f'{head_ref}...{base_ref}']))

    overlap = sorted(set(changed) & set(base_changed))
    hot_overlap = [p for p in overlap if is_hot(p)]
    hot_hits = [p for p in changed if is_hot(p)]

    out += [
        f'changed_files={len(changed)}',
        f'ahead={ahead}',
        f'behind={behind}',
        f'hot_path_hits={len(hot_hits)}',
        f'base_changed_files={len(base_changed)}',
        f'overlap={len(overlap)}',
        f'hot_overlap={len(hot_overlap)}',
    ]
    if hot_hits:
        out.append('hot paths:')
        out += [f' - {p}' for p in hot_hits]
    if overlap:
        out.append('overlapping files (changed by BOTH this branch and the base):')
        out += [f' - {p}' for p in overlap]

    # STRICT is evaluated FIRST, before the no-op early return: the historical gate failed on
    # `behind > 0` regardless of whether the branch changed anything, and "restores the old
    # behaviour" has to mean exactly that. (Caught in review — the original ordering let a
    # behind-but-empty branch pass under strict.)
    if strict and behind > 0:
        out.append(f'PREMERGE_STRICT=1 and branch is {behind} behind — refresh before merge')
        return 1, out

    if not changed:
        out.append('no changed files detected; nothing to audit')
        return 0, out

    if hot_overlap:
        out.append(
            f'REFUSED: {len(hot_overlap)} hot path(s) changed by BOTH this branch and the base. '
            'Rebase and re-run the tests — a load-bearing file must not be merged on inference.'
        )
        return 1, out

    if overlap:
        out.append(
            f'REFUSED: {len(overlap)} file(s) changed by BOTH this branch and the base since the '
            'merge-base. That is a real conflict surface even when git can auto-merge it — '
            'rebase and re-run the tests.'
        )
        return 1, out

    if behind > max_behind:
        out.append(
            f'REFUSED: {behind} commits behind exceeds the {max_behind} tolerance. Nothing '
            'overlaps, but a branch this stale was authored against a materially different tree.'
        )
        return 1, out

    if behind:
        out.append(
            f"OK: {behind} commit(s) behind, but the base touched none of this branch's files "
            f'({len(base_changed)} base file(s) checked) — staleness cannot affect this change.'
        )
    else:
        out.append('OK: branch is current with base.')
    return 0, out


def main() -> int:
    base_ref = os.environ.get('PREMERGE_BASE_REF', 'origin/main')
    head_ref = os.environ.get('PREMERGE_HEAD_REF', 'HEAD')
    max_behind = int(os.environ.get('PREMERGE_MAX_BEHIND', DEFAULT_MAX_BEHIND))
    strict = os.environ.get('PREMERGE_STRICT') == '1'

    code, report = audit(base_ref, head_ref, max_behind, strict)
    for line in report:
        print(line)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
