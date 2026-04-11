#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLICE = ROOT / "apps" / "storage-promotion"
REQUIRED = [
    SLICE / "typedb_live_apply.py",
    SLICE / "pipeline_platform_live.py",
]


def fail(msg: str) -> int:
    print(f"ERR: {msg}", file=sys.stderr)
    return 2


def main() -> int:
    for path in REQUIRED:
        if not path.exists():
            return fail(f"missing required file: {path.relative_to(ROOT)}")

    proc = subprocess.run(
        [sys.executable, str(SLICE / "pipeline_platform_live.py"), "--apply-typedb-live"],
        cwd=str(SLICE),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return fail(f"live pipeline failed: {proc.stderr.strip()}")

    try:
        result = json.loads(proc.stdout)
    except Exception as exc:
        return fail(f"pipeline output is not valid JSON: {exc}")

    typedb_result = result.get("typedb_result")
    if typedb_result is None:
        return fail("typedb_result missing from live pipeline output")
    if typedb_result.get("mode") != "typedb-live-apply":
        return fail("unexpected typedb live mode marker")
    if result["event_envelope"]["event_type"] != "storage.promotion.completed":
        return fail("unexpected event type")
    if result["evidence_receipt"]["status"] != "succeeded":
        return fail("unexpected receipt status")

    print("OK: storage live TypeDB mode validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
