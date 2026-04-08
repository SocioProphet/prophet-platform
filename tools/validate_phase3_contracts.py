#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "contracts/EventEnvelope.v0.1.json",
    "contracts/EvidenceReceipt.v0.1.json",
    "contracts/MembraneDecision.v0.1.json",
    "contracts/CarrierIngested.v0.1.json",
    "contracts/ScopeRef.v0.1.json",
    "contracts/ExportApproved.v0.1.json",
    "contracts/ExportDenied.v0.1.json",
    "apps/lampstand/README.md",
    "apps/lampstand/UPSTREAM_IMPORT.md",
    "apps/lampstand/packaging/systemd/lampstand.service",
]

def fail(msg: str) -> int:
    print(f"ERR: {msg}", file=sys.stderr)
    return 2

def main() -> int:
    for rel in REQUIRED:
        p = ROOT / rel
        if not p.exists():
            return fail(f"missing required phase3 file: {rel}")

    for rel in REQUIRED:
        if rel.endswith(".json"):
            try:
                json.loads((ROOT / rel).read_text(encoding="utf-8"))
            except Exception as exc:
                return fail(f"invalid json in {rel}: {exc}")

    print("OK: phase3 contracts and lampstand staging files present")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
