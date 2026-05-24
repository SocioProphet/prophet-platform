#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LIFT = ROOT / "tools" / "lift_repo_governance_rdf.py"


REQUIRED_TOKENS = [
    "rg:Observation",
    "rg:Repository",
    "rg:SourceArtifact",
    "repo_governance_replay_manifest",
    "mutation_authorized",
    "observation_digest",
]


def fail(msg: str) -> None:
    print(f"ERR: {msg}", file=sys.stderr)


def main() -> int:
    text = LIFT.read_text(encoding="utf-8")
    failed = False

    for token in REQUIRED_TOKENS:
        if token not in text:
            fail(f"missing semantic token: {token}")
            failed = True

    if failed:
        return 1

    print("OK: repo governance semantic replay validates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
