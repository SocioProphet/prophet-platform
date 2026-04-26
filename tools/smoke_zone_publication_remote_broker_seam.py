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
REMOTE_TRANSPORT = "transport://kafka/remote"


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["SOCIOPROFIT_DATA_HOME"] = str(root / "data")
        os.environ["SOCIOPROFIT_STATE_HOME"] = str(root / "state")
        os.environ["SOCIOPROFIT_RUNTIME_HOME"] = str(root / "run")
        os.environ.pop("ZONE_ROUTER_KAFKA_BOOTSTRAP_SERVERS", None)
        os.environ.pop("ZONE_ROUTER_KAFKA_TOPIC_PREFIX", None)

        sample = root / "sample.txt"
        sample.write_text("zone publication remote broker seam smoke\n", encoding="utf-8")

        ingest_result = ingest_path(file_path=str(sample), zone_ref=ZONE_REF)
        plan = plan_publication_request(ingest_result["publication_request"])
        record_result = write_publication_record(plan)
        publish_result = publish_publication_record(record_path=record_result["record_path"], transport_ref=REMOTE_TRANSPORT)
        outcome = publish_result["outcome"]
        failure = publish_result["failure"]

        checks = {
            "ingest_ok": ingest_result.get("ok") is True,
            "plan_ok": plan.get("ok") is True,
            "record_ok": record_result.get("ok") is True,
            "publish_failed": publish_result.get("ok") is False,
            "failure_path_exists": Path(publish_result["failure_path"]).exists(),
            "outcome_path_exists": Path(publish_result["outcome_path"]).exists(),
            "failure_transport_kind": failure.get("transport_kind") == "kafka-remote",
            "failure_mentions_config": "requires configuration" in failure.get("error", ""),
            "failure_mentions_bootstrap": "ZONE_ROUTER_KAFKA_BOOTSTRAP_SERVERS" in failure.get("error", ""),
            "failure_mentions_topic_prefix": "ZONE_ROUTER_KAFKA_TOPIC_PREFIX" in failure.get("error", ""),
            "outcome_status_failed": outcome.get("status") == "failed",
            "outcome_transport_kind": outcome.get("transport_kind") == "kafka-remote",
            "outcome_failure_ref_matches": outcome.get("failure_ref") == publish_result.get("failure_path"),
            "outcome_error_mentions_config": "requires configuration" in outcome.get("error", ""),
        }
        ok = all(checks.values())
        print(json.dumps({"ok": ok, "checks": checks, "failure": failure, "outcome": outcome}, indent=2, sort_keys=True))
        return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
