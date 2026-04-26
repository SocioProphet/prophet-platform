#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/lampstand/src"))
sys.path.insert(0, str(ROOT / "apps/zone-router/src"))

from prophet_platform_lampstand.ingest import ingest_path  # noqa: E402
from zone_router.outbox import write_publication_record  # noqa: E402
from zone_router.planner import plan_publication_request  # noqa: E402
from zone_router.publish import publish_publication_record  # noqa: E402

ZONE_REF = "zone://edge"
EXPECTED_TOPIC = "zone.edge.carrier.ingested.v1"


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["SOCIOPROFIT_DATA_HOME"] = str(root / "data")
        os.environ["SOCIOPROFIT_STATE_HOME"] = str(root / "state")
        os.environ["SOCIOPROFIT_RUNTIME_HOME"] = str(root / "run")

        sample = root / "sample.txt"
        sample.write_text("zone publication local publish smoke\n", encoding="utf-8")

        ingest_result = ingest_path(file_path=str(sample), zone_ref=ZONE_REF)
        plan = plan_publication_request(ingest_result["publication_request"])
        record_result = write_publication_record(plan)
        publish_result = publish_publication_record(record_path=record_result["record_path"])
        outcome = publish_result["outcome"]
        delivery = publish_result["delivery"]

        checks = {
            "ingest_ok": ingest_result.get("ok") is True,
            "plan_ok": plan.get("ok") is True,
            "record_ok": record_result.get("ok") is True,
            "publish_ok": publish_result.get("ok") is True,
            "record_path_exists": Path(record_result["record_path"]).exists(),
            "outcome_path_exists": Path(publish_result["outcome_path"]).exists(),
            "delivery_path_exists": Path(publish_result["delivery_path"]).exists(),
            "topic_log_path_exists": Path(publish_result["topic_log_path"]).exists(),
            "delivery_transport_kind": delivery.get("transport_kind") == "local-jsonl",
            "delivery_publication_id_matches": delivery.get("publication_id") == record_result["record"].get("publication_id"),
            "delivery_topic_expected": delivery.get("topic") == EXPECTED_TOPIC,
            "outcome_status_published": outcome.get("status") == "published",
            "outcome_publication_id_matches": outcome.get("publication_id") == record_result["record"].get("publication_id"),
            "outcome_topic_expected": outcome.get("topic") == EXPECTED_TOPIC,
            "outcome_delivery_ref_matches": outcome.get("delivery_ref") == publish_result.get("delivery_path"),
            "outcome_delivery_id_matches": outcome.get("delivery_id") == delivery.get("delivery_id"),
            "outcome_topic_log_ref_matches": outcome.get("topic_log_ref") == publish_result.get("topic_log_path"),
            "outcome_record_ref_matches": outcome.get("publication_record_ref") == str(Path(record_result["record_path"]).resolve()),
            "outcome_catalog_ref_matches": outcome.get("catalog_ref") == record_result["record"].get("catalog_ref"),
            "outcome_receipt_ref_matches": outcome.get("receipt_ref") == record_result["record"].get("receipt_ref"),
            "outcome_event_ref_matches": outcome.get("event_ref") == record_result["record"].get("event_ref"),
        }
        ok = all(checks.values())
        print(json.dumps({"ok": ok, "checks": checks, "record": record_result["record"], "delivery": delivery, "outcome": outcome}, indent=2, sort_keys=True))
        return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
