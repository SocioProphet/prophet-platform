#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "standards.lock.yaml"


def fail(msg: str) -> None:
    print(f"ERR: {msg}", file=sys.stderr)
    raise SystemExit(2)


def main() -> int:
    if not LOCK.exists():
        fail("missing standards.lock.yaml")
    text = LOCK.read_text(encoding="utf-8", errors="replace")
    required = [
        "kind: StandardsLock",
        "tritrpc:",
        "ontogenesis:",
        "semantic-serdes:",
        "standards-storage:",
        "identity-prime-reference:",
        "hdt-reference:",
        "lampstand:",
    ]
    for needle in required:
        if needle not in text:
            fail(f"standards.lock.yaml missing required section: {needle}")
    print("OK: standards lock structure checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
