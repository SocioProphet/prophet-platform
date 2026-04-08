#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/lampstand/src"))

from prophet_platform_lampstand.catalog import read_entries  # type: ignore
from prophet_platform_lampstand.ingest import ingest_path  # type: ignore


def fail(msg: str) -> None:
    print(f"ERR: {msg}", file=sys.stderr)
    raise SystemExit(2)


def main() -> int:
    required = [
        ROOT / "contracts/CarrierIngested.v0.1.json",
        ROOT / "contracts/EventEnvelope.v0.1.json",
        ROOT / "contracts/EvidenceReceipt.v0.1.json",
        ROOT / "contracts/ReceiptCatalogEntry.v0.1.json",
        ROOT / "apps/lampstand/src/prophet_platform_lampstand/main.py",
        ROOT / "apps/lampstand/src/prophet_platform_lampstand/ingest.py",
        ROOT / "apps/lampstand/src/prophet_platform_lampstand/catalog.py",
    ]
    for path in required:
        if not path.exists():
            fail(f"missing required file: {path.relative_to(ROOT)}")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        sample = root / "sample.txt"
        sample.write_text("phase4 vertical slice\n", encoding="utf-8")
        os.environ["SOCIOPROFIT_STATE_HOME"] = str(root / "state")

        result = ingest_path(file_path=str(sample), scope_ref="scope://local/default")
        for key in ["payload_path", "event_path", "receipt_path", "catalog_path"]:
            if key not in result:
                fail(f"ingest result missing {key}")
            if not Path(result[key]).exists():
                fail(f"{key} does not exist: {result[key]}")

        payload = json.loads(Path(result["payload_path"]).read_text(encoding="utf-8"))
        event = json.loads(Path(result["event_path"]).read_text(encoding="utf-8"))
        receipt = json.loads(Path(result["receipt_path"]).read_text(encoding="utf-8"))
        items = read_entries(limit=5)

        if payload["service_ref"] != "apps/lampstand":
            fail("unexpected payload service_ref")
        if event["event_type"] != "carrier.ingested":
            fail("unexpected event_type")
        if receipt["status"] != "succeeded":
            fail("unexpected receipt status")
        if payload["event_id"] != event["correlation_id"] or payload["event_id"] != receipt["correlation_id"]:
            fail("correlation mismatch across artifacts")
        if not items:
            fail("catalog is empty")
        if items[0]["payload_ref"] != f"file://{Path(result['payload_path']).resolve()}":
            fail("catalog payload_ref mismatch")

    print("OK: phase4 vertical slice validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
