#!/usr/bin/env python3
"""Prove-it-fires for check_workflow_timeout_bounds.py.

Teeth in BOTH directions (the estate's first rule): we make the auditor go RED
on a planted unbounded job before we trust it GREEN on a bounded one.  An
auditor only ever observed passing is indistinguishable from one that cannot
fail.  Named `selftest_*` so no pytest run auto-collects it; run directly:

    python3 tools/selftest_check_workflow_timeout_bounds.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDITOR = HERE / "check_workflow_timeout_bounds.py"

UNBOUNDED = """\
name: unbounded
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
"""

BOUNDED = """\
name: bounded
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - run: echo hi
"""

BAD_VALUE = """\
name: bad
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 0
    steps:
      - run: echo hi
"""

REUSABLE = """\
name: reusable-caller
on: [push]
jobs:
  call:
    uses: org/repo/.github/workflows/x.yml@main
"""

BROKEN_YAML = """\
name: broken
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
    this: [is: not: valid
"""


def run_auditor(workflows_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(AUDITOR), "--workflows-dir", str(workflows_dir)],
        capture_output=True, text=True,
    )


def case(name: str, files: dict[str, str], expect_rc: int, expect_substr: str) -> bool:
    with tempfile.TemporaryDirectory() as td:
        wd = Path(td)
        for fn, body in files.items():
            (wd / fn).write_text(body, encoding="utf-8")
        cp = run_auditor(wd)
        ok = cp.returncode == expect_rc and expect_substr in (cp.stdout + cp.stderr)
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}: rc={cp.returncode} (want {expect_rc}), "
              f"substr {'found' if expect_substr in (cp.stdout+cp.stderr) else 'MISSING'!r}={expect_substr!r}")
        if not ok:
            print("---- captured output ----")
            print(cp.stdout)
            print(cp.stderr)
            print("-------------------------")
        return ok


def main() -> int:
    results = [
        # KNOWN POSITIVE: an unbounded job MUST turn the auditor red.
        case("known-positive: unbounded job -> RED",
             {"unbounded.yml": UNBOUNDED}, 1, "UNBOUNDED jobs"),
        # KNOWN NEGATIVE: a bounded job MUST be green.
        case("known-negative: bounded job -> GREEN",
             {"bounded.yml": BOUNDED}, 0, "every job is bounded"),
        # timeout-minutes: 0 is not a real bound.
        case("bad value: timeout-minutes 0 -> RED",
             {"bad.yml": BAD_VALUE}, 1, "not a positive integer"),
        # reusable-workflow call is exempt (green) but surfaced.
        case("reusable-workflow call -> GREEN but listed",
             {"reusable.yml": REUSABLE}, 0, "reusable-workflow calls"),
        # unparseable YAML fails closed, never silently skipped.
        case("broken YAML -> RED (fail-closed)",
             {"broken.yml": BROKEN_YAML}, 1, "PARSE ERRORS"),
        # empty scan is a failure, not a pass.
        case("empty dir -> RED (no green from nothing)",
             {}, 1, "refusing to report green"),
        # mixed: one bounded, one unbounded -> RED, and names the unbounded one.
        case("mixed set -> RED and names offender",
             {"a.yml": BOUNDED, "b.yml": UNBOUNDED}, 1, "b.yml:build"),
    ]
    passed = sum(results)
    print(f"\n{passed}/{len(results)} cases passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
