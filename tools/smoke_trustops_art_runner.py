#!/usr/bin/env python3
"""Smoke the synthetic TrustOps ART-smoke runner and validate its receipt."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "apps" / "trustops-art-runner" / "examples" / "functional-service.art-smoke.manifest.json"
OUTPUT = ROOT / "build" / "trustops-art-runner" / "trustops-receipt.art-smoke.json"
RUNNER = ROOT / "apps" / "trustops-art-runner" / "src"
VALIDATOR = ROOT / "tools" / "validate_trustops_art_receipt.py"


def run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
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
            "trustops_art_runner.cli",
            "run",
            "--profile",
            "art-smoke",
            "--manifest",
            str(MANIFEST),
            "--generated-at",
            "2026-05-26T22:30:00Z",
            "--output",
            str(OUTPUT),
        ]
    )
    run([sys.executable, str(VALIDATOR), str(OUTPUT)])
    print(f"OK: emitted and validated {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(RUNNER))
    raise SystemExit(main())
