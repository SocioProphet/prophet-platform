#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    ROOT / "docs" / "banking-runtime-slices.md",
    ROOT / "contracts" / "EventEnvelope.v0.1.json",
    ROOT / "contracts" / "EvidenceReceipt.v0.1.json",
    ROOT / "apps" / "banking-twin-ingest" / "README.md",
    ROOT / "apps" / "banking-scenario-run" / "README.md",
    ROOT / "apps" / "banking-capital-rollforward" / "README.md",
    ROOT / "apps" / "banking-filing-assembler" / "README.md",
]

def fail(msg: str) -> int:
    print(f"ERR: {msg}", file=sys.stderr)
    return 2

def main() -> int:
    for path in REQUIRED:
        if not path.exists():
            return fail(f"missing required file: {path.relative_to(ROOT)}")
    print("OK: banking runtime staging scaffolds present")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
