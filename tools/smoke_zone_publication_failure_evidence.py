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
FAIL_TRANSPORT = "transport://fail/test"
EXPECTED_TOPIC = "zone.edge.carrier.ingested.v1"


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["SOCIOPROFIT_DATA_HOME"] = str(root / "data")
        os.environ["SOCIOPROFIT_STATE_HOME"] = str(root / "state")
        os.environ["SOCIOPROFIT_RUNTIME_HOME"] = str(root / "run")

        sample = root / "sample.txt"
        sample.write_text("zone publication failure evidence smoke\n", encoding="utf-8")

        ingest_result = ingest_path(file_path=str(sample), zone_ref=ZONE_REF)
        plan = plan_publication_request(ingest_result["publication_request"])
        record_result = write_publication_record(plan)
        publish_result = publish_publication_record(record_path=record_result["record_path"], transport_ref=FAIL_TRANSPORT)
        outcome = publish_result["outcome"]
        failure = publish_result["failure"]

        checks = {
            "ingest_ok": ingest_result.get("ok") is True,
            "plan_ok": plan.get("ok") is True,
            "record_ok": record_result.get("ok") is True,
            "publish_failed": publish_result.get("ok") is False,
            "failure_path_exists": Path(publish_result["failure_path"]).exists(),
            "outcome_path_exists": Path(publish_result["outcome_path"]).exists(),
            "failure_transport_kind": failure.get("transport_kind") == "fail-test",
            "failure_publication_id_matches": failure.get("publication_id") == record_result["record"].get("publication_id"),
            "failure_topic_expected": failure.get("topic") == EXPECTED_TOPIC,
            "outcome_status_failed": outcome.get("status") == "failed",
            "outcome_failure_ref_matches": outcome.get("failure_ref") == publish_result.get("failure_path"),
            "outcome_failure_id_matches": outcome.get("failure_id") == failure.get("failure_id"),
            "outcome_publication_id_matches": outcome.get("publication_id") == record_result["record"].get("publication_id"),
            "outcome_error_present": bool(outcome.get("error")),
            "outcome_record_ref_matches": outcome.get("publication_record_ref") == str(Path(record_result["record_path"]).resolve()),
            "outcome_catalog_ref_matches": outcome.get("catalog_ref") == record_result["record"].get("catalog_ref"),
            "outcome_receipt_ref_matches": outcome.get("receipt_ref") == record_result["record"].get("receipt_ref"),
            "outcome_event_ref_matches": outcome.get("event_ref") == record_result["record"].get("event_ref"),
        }
        ok = all(checks.values())
        print(json.dumps({"ok": ok, "checks": checks, "record": record_result["record"], "failure": failure, "outcome": outcome}, indent=2, sort_keys=True))
        return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
