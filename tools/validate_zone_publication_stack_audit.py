#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "ZONE_PUBLICATION_STACK_AUDIT.md"
REQUIRED_TERMS = [
    "#142",
    "#156",
    "#173",
    "semantic-bridge validation",
    "zone-router semantic gate integration",
    "adapterized transport modes",
    "retry and attempt state",
    "Sociosphere build-intelligence registration after merge",
]


def main() -> int:
    if not AUDIT.exists():
        raise SystemExit(f"missing audit file: {AUDIT.relative_to(ROOT)}")
    text = AUDIT.read_text(encoding="utf-8")
    missing = [term for term in REQUIRED_TERMS if term not in text]
    if missing:
        raise SystemExit("zone publication stack audit missing required terms: " + ", ".join(missing))
    print("zone publication stack audit validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
