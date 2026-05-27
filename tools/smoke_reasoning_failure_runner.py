#!/usr/bin/env python3
"""Smoke the synthetic reasoning-failure runner and validate its receipt."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER_SRC = ROOT / "apps" / "reasoning-failure-runner" / "src"
CASE = ROOT / "apps" / "reasoning-failure-runner" / "examples" / "exact-string-case.json"
SUITE = ROOT / "apps" / "reasoning-failure-runner" / "examples" / "exactness-perturbations.json"
OUTPUT = ROOT / "build" / "reasoning-failure-runner" / "reasoning-failure-receipt.json"
VALIDATOR = ROOT / "tools" / "validate_reasoning_failure_receipt.py"


def run(cmd: list[str]) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(RUNNER_SRC)
    result = subprocess.run(cmd, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout, file=sys.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            sys.executable,
            "-m",
            "reasoning_failure_runner.cli",
            "run",
            "--case",
            str(CASE),
            "--suite",
            str(SUITE),
            "--generated-at",
            "2026-05-26T23:25:00Z",
            "--out",
            str(OUTPUT),
        ]
    )
    run([sys.executable, str(VALIDATOR), str(OUTPUT)])
    print(f"OK: emitted and validated {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
