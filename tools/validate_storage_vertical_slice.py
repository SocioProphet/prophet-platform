#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLICE = ROOT / "apps" / "storage-promotion"

REQUIRED = [
    ROOT / "contracts" / "storage" / "Observation.v0.1.json",
    ROOT / "contracts" / "storage" / "RunRecord.v0.1.json",
    ROOT / "contracts" / "storage" / "ProjectionManifest.v0.1.json",
    ROOT / "contracts" / "storage" / "PromotionRejection.v0.1.json",
    ROOT / "contracts" / "storage" / "PromotionReceipt.v0.1.json",
    SLICE / "runtime.py",
    SLICE / "dolt_adapter.py",
    SLICE / "typedb_adapter.py",
    SLICE / "pipeline.py",
]


def fail(msg: str) -> int:
    print(f"ERR: {msg}", file=sys.stderr)
    return 2


def main() -> int:
    for path in REQUIRED:
        if not path.exists():
            return fail(f"missing required file: {path.relative_to(ROOT)}")

    proc = subprocess.run(
        [sys.executable, str(SLICE / "pipeline.py")],
        cwd=str(SLICE),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return fail(f"pipeline failed: {proc.stderr.strip()}")

    try:
        result = json.loads(proc.stdout)
    except Exception as exc:
        return fail(f"pipeline output is not valid JSON: {exc}")

    if result["observation"]["normalized_payload"]["subject"] != "user123":
        return fail("unexpected subject in observation")
    if result["promoted"]["claim"]["type"] != "has_role":
        return fail("unexpected claim type")
    if result["projection"]["projection_manifest"]["target_store"] != "neo4j":
        return fail("unexpected projection target store")

    print("OK: storage vertical slice validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
