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
SUCCESS_TRANSPORT = "transport://local/jsonl"
EXPECTED_TOPIC = "zone.edge.carrier.ingested.v1"


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["SOCIOPROFIT_DATA_HOME"] = str(root / "data")
        os.environ["SOCIOPROFIT_STATE_HOME"] = str(root / "state")
        os.environ["SOCIOPROFIT_RUNTIME_HOME"] = str(root / "run")

        sample = root / "sample.txt"
        sample.write_text("zone publication retry state smoke\n", encoding="utf-8")

        ingest_result = ingest_path(file_path=str(sample), zone_ref=ZONE_REF)
        plan = plan_publication_request(ingest_result["publication_request"])
        record_result = write_publication_record(plan)
        record_path = record_result["record_path"]

        failed_publish = publish_publication_record(record_path=record_path, transport_ref=FAIL_TRANSPORT)
        success_publish = publish_publication_record(record_path=record_path, transport_ref=SUCCESS_TRANSPORT)

        failed = failed_publish["outcome"]
        succeeded = success_publish["outcome"]

        checks = {
            "ingest_ok": ingest_result.get("ok") is True,
            "plan_ok": plan.get("ok") is True,
            "record_ok": record_result.get("ok") is True,
            "first_publish_failed": failed_publish.get("ok") is False,
            "second_publish_succeeded": success_publish.get("ok") is True,
            "first_attempt_is_one": failed.get("attempt") == 1,
            "first_status_failed": failed.get("status") == "failed",
            "first_retry_eligible": failed.get("retry_eligible") is True,
            "first_previous_is_none": failed.get("previous_outcome_id") is None,
            "second_attempt_is_two": succeeded.get("attempt") == 2,
            "second_status_published": succeeded.get("status") == "published",
            "second_retry_not_eligible": succeeded.get("retry_eligible") is False,
            "second_retry_after_failure": succeeded.get("retry_after_failure") is True,
            "second_previous_id_matches": succeeded.get("previous_outcome_id") == failed.get("outcome_id"),
            "second_previous_status_failed": succeeded.get("previous_outcome_status") == "failed",
            "second_previous_ref_matches": succeeded.get("previous_outcome_ref") == failed.get("outcome_ref"),
            "same_publication_id": succeeded.get("publication_id") == failed.get("publication_id") == record_result["record"].get("publication_id"),
            "topic_expected": succeeded.get("topic") == EXPECTED_TOPIC,
            "success_delivery_exists": Path(success_publish["delivery_path"]).exists(),
            "failure_evidence_exists": Path(failed_publish["failure_path"]).exists(),
        }
        ok = all(checks.values())
        print(json.dumps({"ok": ok, "checks": checks, "failed": failed, "succeeded": succeeded}, indent=2, sort_keys=True))
        return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
