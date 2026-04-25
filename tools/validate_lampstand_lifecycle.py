#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/lampstand/src"))
sys.path.insert(0, str(ROOT / "apps/zone-router/src"))

from prophet_platform_lampstand.catalog import read_entries  # noqa: E402
from prophet_platform_lampstand.ingest import ingest_path  # noqa: E402
from zone_router.planner import plan_publication_request  # noqa: E402

ZONE_REF = "zone://edge"
TOPIC_REF = "topic://lampstand/lifecycle-smoke"
EXPECTED_TOPIC = "zone.edge.carrier.ingested.v1"


def path_from_file_uri(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ValueError(f"expected file URI, got {uri}")
    return Path(parsed.path)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["SOCIOPROFIT_DATA_HOME"] = str(root / "data")
        os.environ["SOCIOPROFIT_STATE_HOME"] = str(root / "state")
        os.environ["SOCIOPROFIT_RUNTIME_HOME"] = str(root / "run")

        sample = root / "sample.txt"
        sample.write_text("lampstand lifecycle validation smoke\n", encoding="utf-8")

        result = ingest_path(file_path=str(sample), zone_ref=ZONE_REF, topic_ref=TOPIC_REF)
        request = result["publication_request"]
        plan = plan_publication_request(request)
        entries = read_entries(limit=10)
        latest = entries[0] if entries else {}

        payload_path = Path(result["payload_path"])
        event_path = Path(result["event_path"])
        receipt_path = Path(result["receipt_path"])
        catalog_path = Path(result["catalog_path"])

        checks = {
            "result_ok": result.get("ok") is True,
            "payload_exists": payload_path.exists(),
            "event_exists": event_path.exists(),
            "receipt_exists": receipt_path.exists(),
            "catalog_exists": catalog_path.exists(),
            "catalog_has_latest_entry": bool(latest),
            "catalog_entry_matches_carrier": latest.get("subject_ref") == result.get("carrier_ref"),
            "catalog_entry_matches_receipt": path_from_file_uri(latest.get("receipt_ref", "file:///missing")) == receipt_path.resolve(),
            "catalog_entry_matches_payload": path_from_file_uri(latest.get("payload_ref", "file:///missing")) == payload_path.resolve(),
            "request_has_catalog_ref": request.get("catalog_ref") == result.get("catalog_path"),
            "request_has_receipt_ref": request.get("receipt_ref") == result.get("receipt_path"),
            "request_has_event_ref": request.get("event_ref") == result.get("event_path"),
            "request_has_zone": request.get("zone_ref") == ZONE_REF,
            "request_has_topic_ref": request.get("topic_ref") == TOPIC_REF,
            "plan_ok": plan.get("ok") is True,
            "plan_mode_resolved": plan.get("publication_mode") == "resolved",
            "plan_topic_expected": plan.get("topic") == EXPECTED_TOPIC,
            "plan_event_type": plan.get("event_type") == "carrier.ingested",
        }
        ok = all(checks.values())
        print(json.dumps({"ok": ok, "checks": checks, "publication_request": request, "plan": plan, "latest_catalog_entry": latest}, indent=2, sort_keys=True))
        return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
