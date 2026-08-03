#!/usr/bin/env python3
"""`make preflight` (L5): local == CI parity.

Runs the fast, hermetic subset of the REQUIRED `validate-target-diagnostics` matrix locally so
a developer catches path-breaks and gate failures BEFORE pushing, instead of only in CI after a
slow round-trip. Each leg is an existing `make` target, run exactly as CI runs it, so a green
preflight means those legs will be green in CI too.

INCLUDED (fast + hermetic, laptop-runnable in minutes):
  * validate-repo, drift-check, standards-check, topology-check   — repo/standards/topology gates
  * rollout-analysis-refs-check, overlay-self-contained-check     — static ref-resolution (INV-DEP-9/10)
  * no-dangling-path-refs-check                                   — blast-radius on refactor (INV-DEP-12)
  * evidence-refs-check                                           — evidence-reference verification (INV-DEP-13)
  * test-tools                                                    — the tools/ pytest suite

DELIBERATELY EXCLUDED — these stay in CI, never in preflight:
  * the ephemeral real-apply / digest-exists preflight and the wave-promote GATE chain (need
    cluster/registry credentials),
  * kind, `go build`/test-go, per-app venvs (app-test-diagnostics), docker and the smoke matrix.
  These are infra-heavy or non-hermetic; running them on a laptop would make preflight slow and
  flaky, defeating its purpose. They remain fully covered by the required CI matrix.

Prints a PASS / what-to-fix summary and exits non-zero if any leg fails.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Order matters only for readability: cheapest gates first, the pytest suite last.
LEGS: list[str] = [
    "validate-repo",
    "drift-check",
    "standards-check",
    "topology-check",
    "rollout-analysis-refs-check",
    "overlay-self-contained-check",
    "manifest-completeness-check",
    "no-dangling-path-refs-check",
    "evidence-refs-check",
    "test-tools",
]

# Legs that shell out to `kubectl kustomize` to render overlays. Without kubectl they fail
# closed (correct in CI), but locally we want to tell the developer WHY rather than dump a
# confusing traceback.
_NEEDS_KUBECTL = {
    "rollout-analysis-refs-check",
    "overlay-self-contained-check",
    "manifest-completeness-check",
}


def _run_leg(target: str) -> tuple[bool, float, str]:
    start = time.monotonic()
    proc = subprocess.run(
        ["make", target],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    dur = time.monotonic() - start
    ok = proc.returncode == 0
    output = (proc.stdout or "") + (proc.stderr or "")
    return ok, dur, output


def main() -> int:
    kubectl = shutil.which("kubectl") is not None
    print("make preflight (L5) — local == CI parity for the fast, hermetic required matrix")
    print(f"  running {len(LEGS)} leg(s) from {ROOT}\n")
    if not kubectl:
        print(
            "  NOTE: kubectl not found — the overlay-render gates (INV-DEP-9/10) will fail "
            "closed. Install kubectl to run them locally (`brew install kubectl`).\n"
        )

    results: list[tuple[str, bool, float]] = []
    failures: list[tuple[str, str]] = []
    for target in LEGS:
        label = target + (" (needs kubectl)" if target in _NEEDS_KUBECTL and not kubectl else "")
        print(f"  -> {label} ...", flush=True)
        ok, dur, output = _run_leg(target)
        results.append((target, ok, dur))
        status = "PASS" if ok else "FAIL"
        print(f"     {status} ({dur:.1f}s)")
        if not ok:
            failures.append((target, output))

    print("\n" + "=" * 72)
    total = sum(d for _, _, d in results)
    for target, ok, dur in results:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {target:<32} {dur:6.1f}s")
    print(f"  total: {total:.1f}s")
    print("=" * 72)

    if not failures:
        print(
            "\nPREFLIGHT PASSED. The fast required-matrix legs are green locally. The infra-heavy "
            "legs (kind, test-go, per-app venvs, docker, smoke) and the CI-only real-apply / "
            "digest-exists preflight still run in CI."
        )
        return 0

    print(f"\nPREFLIGHT FAILED — {len(failures)} leg(s) need attention:\n")
    for target, output in failures:
        print(f"----- {target} -----")
        tail = "\n".join(output.rstrip().splitlines()[-25:])
        print(tail if tail else "(no output captured)")
        print()
    print("Fix the leg(s) above, then re-run `make preflight`. Do not push until it is green.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
