#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "tools" / "emit_repo_governance_replay_ledger.py"

REQUIRED_TOKENS = [
    "repo_governance_replay_ledger_record",
    "repo_governance_replay_signature_envelope",
    "record_digest",
    "sha256",
    "unsigned-local-placeholder",
    "mutation_authorized",
]


def fail(msg: str) -> None:
    print(f"ERR: {msg}", file=sys.stderr)


def main() -> int:
    text = LEDGER.read_text(encoding="utf-8")
    failed = False

    for token in REQUIRED_TOKENS:
        if token not in text:
            fail(f"missing replay ledger token: {token}")
            failed = True

    if failed:
        return 1

    print("OK: repo governance replay ledger validates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
