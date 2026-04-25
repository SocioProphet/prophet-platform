#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/lampstand/src"))
sys.path.insert(0, str(ROOT / "apps/zone-router/src"))

from prophet_platform_lampstand.ingest import ingest_path  # noqa: E402
from zone_router.main import main as zone_router_main  # noqa: E402

ZONE_REF = "zone://edge"
FAIL_TRANSPORT = "transport://fail/test"


def _run_zone_router(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = zone_router_main(argv)
    return rc, json.loads(buf.getvalue())


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["SOCIOPROFIT_DATA_HOME"] = str(root / "data")
        os.environ["SOCIOPROFIT_STATE_HOME"] = str(root / "state")
        os.environ["SOCIOPROFIT_RUNTIME_HOME"] = str(root / "run")

        sample = root / "sample.txt"
        sample.write_text("zone router dead letter smoke\n", encoding="utf-8")

        ingest_result = ingest_path(file_path=str(sample), zone_ref=ZONE_REF)
        request_path = root / "publication_request.json"
        request_path.write_text(json.dumps(ingest_result["publication_request"], indent=2, sort_keys=True) + "\n", encoding="utf-8")

        rc_enqueue, enqueue_payload = _run_zone_router(["enqueue-request", "--path", str(request_path)])
        if rc_enqueue != 0:
            print(json.dumps({"ok": False, "stage": "enqueue-request", "payload": enqueue_payload}, indent=2, sort_keys=True))
            return rc_enqueue

        record_path = Path(enqueue_payload["record_path"])
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["retry_policy"] = {
            "max_attempts": 2,
            "backoff_seconds": 5,
            "strategy": "fixed",
            "dead_letter_on_terminal": True,
        }
        record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        rc_fail_1, fail_1 = _run_zone_router(["publish-record", "--path", str(record_path), "--transport-ref", FAIL_TRANSPORT])
        rc_fail_2, fail_2 = _run_zone_router(["publish-record", "--path", str(record_path), "--transport-ref", FAIL_TRANSPORT])

        checks = {
            "first_failed": rc_fail_1 == 2 and fail_1.get("ok") is False,
            "first_retry_eligible": fail_1.get("outcome", {}).get("retry_eligible") is True,
            "first_terminal": fail_1.get("outcome", {}).get("terminal") is False,
            "second_failed": rc_fail_2 == 2 and fail_2.get("ok") is False,
            "second_retry_eligible": fail_2.get("outcome", {}).get("retry_eligible") is False,
            "second_terminal": fail_2.get("outcome", {}).get("terminal") is True,
            "dead_letter": Path(fail_2.get("dead_letter", {}).get("dead_letter_path", root / "missing")).exists(),
            "attempts": fail_1.get("outcome", {}).get("attempt") == 1 and fail_2.get("outcome", {}).get("attempt") == 2,
        }
        ok = all(checks.values())
        print(json.dumps({"ok": ok, "checks": checks, "first": fail_1, "second": fail_2}, indent=2, sort_keys=True))
        return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
