#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "bundles" / "fogstack.access-v0.1.yaml"
RULEPACK = ROOT / "conformance" / "rulepacks" / "fogstack.access-v0.1.yaml"
VERIFY = ROOT / "tools" / "fogstack_verify.py"


def fail(msg: str) -> None:
    print(f"ERR: {msg}", file=sys.stderr)
    raise SystemExit(2)


for path in [BUNDLE, RULEPACK, VERIFY]:
    if not path.exists():
        fail(f"missing Fog Stack validation input: {path.relative_to(ROOT)}")

cmd = [sys.executable, str(VERIFY), str(BUNDLE), "--rulepack", str(RULEPACK)]
proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
if proc.returncode != 0:
    if proc.stdout:
        print(proc.stdout, end="", file=sys.stderr)
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    fail("Fog Stack access bundle verification failed")

print("OK: Fog Stack access bundle verification passed")
