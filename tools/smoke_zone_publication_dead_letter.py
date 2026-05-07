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
        sample.write_text("zone publication dead-letter smoke\n", encoding="utf-8")

        ingest_result = ingest_path(file_path=str(sample), zone_ref=ZONE_REF)
        plan = plan_publication_request(ingest_result["publication_request"])
        record_result = write_publication_record(plan)
        record_path = Path(record_result["record_path"])
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["retry_policy"] = {
            "version": "0.1",
            "max_attempts": 2,
            "backoff_seconds": 5,
            "strategy": "fixed",
            "dead_letter_on_terminal": True,
        }
        record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        failed_1 = publish_publication_record(record_path=record_path, transport_ref=FAIL_TRANSPORT)
        failed_2 = publish_publication_record(record_path=record_path, transport_ref=FAIL_TRANSPORT)

        first = failed_1["outcome"]
        second = failed_2["outcome"]
        dead_letter = failed_2.get("dead_letter", {})
        checks = {
            "ingest_ok": ingest_result.get("ok") is True,
            "plan_ok": plan.get("ok") is True,
            "record_ok": record_result.get("ok") is True,
            "first_failed": failed_1.get("ok") is False and first.get("status") == "failed",
            "first_attempt": first.get("attempt") == 1,
            "first_retryable": first.get("retry_eligible") is True,
            "first_not_terminal": first.get("terminal") is False,
            "first_next_retry": first.get("next_retry_not_before") is not None,
            "second_failed": failed_2.get("ok") is False and second.get("status") == "failed",
            "second_attempt": second.get("attempt") == 2,
            "second_not_retryable": second.get("retry_eligible") is False,
            "second_terminal": second.get("terminal") is True,
            "second_no_next_retry": second.get("next_retry_not_before") is None,
            "previous_link": second.get("previous_outcome_id") == first.get("outcome_id"),
            "topic_expected": second.get("topic") == EXPECTED_TOPIC,
            "dead_letter_ok": dead_letter.get("ok") is True,
            "dead_letter_exists": Path(dead_letter.get("dead_letter_path", root / "missing")).exists(),
        }
        ok = all(checks.values())
        print(json.dumps({"ok": ok, "checks": checks, "first": first, "second": second, "dead_letter": dead_letter}, indent=2, sort_keys=True))
        return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
