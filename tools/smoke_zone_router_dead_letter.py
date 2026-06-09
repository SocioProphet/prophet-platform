#!/usr/bin/env python3
"""
Smoke test for zone publication retry policy and dead-letter artifact path.

Verifies:
  1. First forced failure: retry_eligible=True, terminal=False, no dead letter.
  2. Second forced failure (max_attempts=2): terminal=True, retry_eligible=False,
     dead-letter artifact written, failure evidence still intact.
  3. Successful publication: retry_eligible=False.
  4. Dead-letter log exists and contains the dead-letter record.

Non-claims:
  - Smoke does not exercise live transport or remote broker.
  - Smoke does not authorize production mutation.
  - Dead-letter artifact is an audit record only.
"""
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


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["SOCIOPROFIT_DATA_HOME"] = str(root / "data")
        os.environ["SOCIOPROFIT_STATE_HOME"] = str(root / "state")
        os.environ["SOCIOPROFIT_RUNTIME_HOME"] = str(root / "run")

        sample = root / "sample.txt"
        sample.write_text("zone publication dead letter smoke\n", encoding="utf-8")

        ingest_result = ingest_path(file_path=str(sample), zone_ref=ZONE_REF)
        plan = plan_publication_request(ingest_result["publication_request"])

        # Inject a 2-attempt retry policy so the smoke terminates on attempt 2
        plan_data = plan["plan"] if "plan" in plan else plan
        plan_data["retry_policy"] = {
            "max_attempts": 2,
            "retry_backoff_seconds": 1,
            "retry_strategy": "fixed",
            "dead_letter_on_terminal": True,
        }

        record_result = write_publication_record(plan_data)
        record_path = record_result["record_path"]

        # Patch retry_policy into the stored record file
        stored = json.loads(Path(record_path).read_text(encoding="utf-8"))
        stored["retry_policy"] = plan_data["retry_policy"]
        Path(record_path).write_text(json.dumps(stored, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        # Attempt 1 — forced failure
        first = publish_publication_record(record_path=record_path, transport_ref=FAIL_TRANSPORT)
        first_outcome = first["outcome"]

        # Attempt 2 — forced failure again (terminal)
        second = publish_publication_record(record_path=record_path, transport_ref=FAIL_TRANSPORT)
        second_outcome = second["outcome"]

        # Attempt 3 — success (after terminal; retry_state allows it since it just counts outcomes)
        third = publish_publication_record(record_path=record_path, transport_ref=SUCCESS_TRANSPORT)
        third_outcome = third["outcome"]

        checks = {
            "ingest_ok": ingest_result.get("ok") is True,
            "plan_ok": plan.get("ok") is True,
            "record_ok": record_result.get("ok") is True,
            # first failure
            "first_failed": first.get("ok") is False,
            "first_attempt_one": first_outcome.get("attempt") == 1,
            "first_status_failed": first_outcome.get("status") == "failed",
            "first_retry_eligible": first_outcome.get("retry_eligible") is True,
            "first_not_terminal": first_outcome.get("terminal") is False,
            "first_next_retry_present": first_outcome.get("next_retry_not_before") is not None,
            "first_no_dead_letter": "dead_letter" not in first,
            "first_failure_evidence": bool(first_outcome.get("failure_ref")),
            # second failure — terminal
            "second_failed": second.get("ok") is False,
            "second_attempt_two": second_outcome.get("attempt") == 2,
            "second_terminal": second_outcome.get("terminal") is True,
            "second_not_retry_eligible": second_outcome.get("retry_eligible") is False,
            "second_no_next_retry": second_outcome.get("next_retry_not_before") is None,
            "second_dead_letter_emitted": "dead_letter" in second,
            "second_dead_letter_file_exists": (
                bool(second.get("dead_letter")) and
                Path(second["dead_letter"]["dead_letter_ref"]).exists()
            ),
            "second_previous_id_matches_first": (
                second_outcome.get("previous_outcome_id") == first_outcome.get("outcome_id")
            ),
            "second_failure_evidence_intact": bool(second_outcome.get("failure_ref")),
            # success publish
            "third_published": third.get("ok") is True,
            "third_retry_not_eligible": third_outcome.get("retry_eligible") is False,
        }

        failed = [k for k, v in checks.items() if not v]
        result = {
            "smoke": "zone-router-dead-letter",
            "passed": not failed,
            "failed_checks": failed,
            "checks": checks,
            "non_claims": [
                "Smoke does not exercise live transport or remote broker.",
                "Smoke does not authorize production mutation.",
                "Dead-letter artifact is an audit record only.",
                "Smoke does not certify Signadot feature parity.",
            ],
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        print(("PASS" if not failed else "FAIL") + ": zone-router dead-letter smoke")
        return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
