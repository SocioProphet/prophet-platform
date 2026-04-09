#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLICE = ROOT / "apps" / "storage-promotion"
REQUIRED = [
    SLICE / "receipts.py",
    SLICE / "pipeline_platform.py",
    SLICE / "runtime.py",
    SLICE / "dolt_adapter.py",
    SLICE / "typedb_adapter.py",
    ROOT / "contracts" / "EventEnvelope.v0.1.json",
    ROOT / "contracts" / "EvidenceReceipt.v0.1.json",
]


def fail(msg: str) -> int:
    print(f"ERR: {msg}", file=sys.stderr)
    return 2


def main() -> int:
    for path in REQUIRED:
        if not path.exists():
            return fail(f"missing required file: {path.relative_to(ROOT)}")

    with tempfile.TemporaryDirectory() as td:
        env = dict(os.environ)
        env["STORAGE_PROMOTION_STATE_HOME"] = str(Path(td) / "state")
        proc = subprocess.run(
            [sys.executable, str(SLICE / "pipeline_platform.py")],
            cwd=str(SLICE),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return fail(f"pipeline platform failed: {proc.stderr.strip()}")
        try:
            result = json.loads(proc.stdout)
        except Exception as exc:
            return fail(f"pipeline output is not valid JSON: {exc}")

        if result["event_envelope"]["event_type"] != "storage.promotion.completed":
            return fail("unexpected event type")
        if result["evidence_receipt"]["status"] != "succeeded":
            return fail("unexpected receipt status")
        if result["event_envelope"]["correlation_id"] != result["promoted"]["claim"]["id"]:
            return fail("correlation id mismatch")
        if not Path(result["event_path"]).exists() or not Path(result["receipt_path"]).exists():
            return fail("expected event/receipt artifacts were not written")

    print("OK: storage receipt vertical slice validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
