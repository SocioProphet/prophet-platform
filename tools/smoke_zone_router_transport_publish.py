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
sys.path.insert(0, str(ROOT / "apps/semantic-bridge/src"))

from prophet_platform_lampstand.ingest import ingest_path  # noqa: E402
from zone_router.main import main as zone_router_main  # noqa: E402

ZONE_REF = "zone://edge"
SUCCESS_TRANSPORT = "transport://kafka/jsonl"
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
        sample.write_text("zone router retry publish smoke\n", encoding="utf-8")

        ingest_result = ingest_path(file_path=str(sample), zone_ref=ZONE_REF)
        request_path = root / "publication_request.json"
        request_path.write_text(json.dumps(ingest_result["publication_request"], indent=2, sort_keys=True) + "\n", encoding="utf-8")

        rc_enqueue, enqueue_payload = _run_zone_router(["enqueue-request", "--path", str(request_path)])
        if rc_enqueue != 0:
            print(json.dumps({"ok": False, "stage": "enqueue-request", "payload": enqueue_payload}, indent=2, sort_keys=True))
            return rc_enqueue

        record_path = enqueue_payload["record_path"]
        rc_fail, fail_payload = _run_zone_router(["publish-record", "--path", str(record_path), "--transport-ref", FAIL_TRANSPORT])
        rc_success, success_payload = _run_zone_router(["publish-record", "--path", str(record_path), "--transport-ref", SUCCESS_TRANSPORT])

        checks = {
            "enqueue_ok": enqueue_payload.get("ok") is True,
            "first_failed": rc_fail == 2 and fail_payload.get("ok") is False,
            "first_attempt": fail_payload.get("outcome", {}).get("attempt") == 1,
            "failure_evidence": Path(fail_payload.get("failure_evidence", {}).get("evidence_path", root / "missing")).exists(),
            "second_success": rc_success == 0 and success_payload.get("ok") is True,
            "second_attempt": success_payload.get("outcome", {}).get("attempt") == 2,
            "previous_outcome_ref": success_payload.get("outcome", {}).get("previous_outcome_ref") == fail_payload.get("outcome", {}).get("outcome_id"),
            "transport_kind": success_payload.get("outcome", {}).get("transport_kind") == "kafka-jsonl",
            "delivery_path": Path(success_payload.get("transport_result", {}).get("delivery_path", root / "missing")).exists(),
            "topic_log_path": Path(success_payload.get("transport_result", {}).get("topic_log_path", root / "missing")).exists(),
        }
        ok = all(checks.values())
        print(json.dumps({"ok": ok, "checks": checks, "failure_payload": fail_payload, "success_payload": success_payload}, indent=2, sort_keys=True))
        return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
