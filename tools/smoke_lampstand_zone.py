#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/lampstand/src"))

from prophet_platform_lampstand.ingest import ingest_path  # noqa: E402


ZONE_REF = "zone://edge"
TOPIC_REF = "zone.edge.carrier.ingested.v1"


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["SOCIOPROFIT_DATA_HOME"] = str(root / "data")
        os.environ["SOCIOPROFIT_STATE_HOME"] = str(root / "state")
        os.environ["SOCIOPROFIT_RUNTIME_HOME"] = str(root / "run")

        sample = root / "sample.txt"
        sample.write_text("lampstand zone smoke\n", encoding="utf-8")

        result = ingest_path(
            file_path=str(sample),
            zone_ref=ZONE_REF,
            topic_ref=TOPIC_REF,
        )

        event = json.loads(Path(result["event_path"]).read_text(encoding="utf-8"))
        receipt = json.loads(Path(result["receipt_path"]).read_text(encoding="utf-8"))
        payload = json.loads(Path(result["payload_path"]).read_text(encoding="utf-8"))
        latest = json.loads((Path(result["catalog_path"]).parent / "latest.json").read_text(encoding="utf-8"))["latest_entry"]

        checks = {
            "result_zone": result.get("zone_ref") == ZONE_REF,
            "result_topic": result.get("topic_ref") == TOPIC_REF,
            "publication_request_zone": result.get("publication_request", {}).get("zone_ref") == ZONE_REF,
            "publication_request_topic": result.get("publication_request", {}).get("topic_ref") == TOPIC_REF,
            "event_zone": event.get("zone_ref") == ZONE_REF,
            "event_topic": event.get("topic_ref") == TOPIC_REF,
            "receipt_zone": receipt.get("zone_ref") == ZONE_REF,
            "receipt_topic": receipt.get("topic_ref") == TOPIC_REF,
            "payload_zone": payload.get("zone_ref") == ZONE_REF,
            "payload_topic": payload.get("topic_ref") == TOPIC_REF,
            "latest_zone": latest.get("zone_ref") == ZONE_REF,
            "latest_topic": latest.get("topic_ref") == TOPIC_REF,
        }
        ok = all(checks.values())
        print(json.dumps({"ok": ok, "checks": checks, "publication_request": result.get("publication_request")}, indent=2, sort_keys=True))
        return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
