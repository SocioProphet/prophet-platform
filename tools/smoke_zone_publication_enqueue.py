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

ZONE_REF = "zone://edge"


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["SOCIOPROFIT_DATA_HOME"] = str(root / "data")
        os.environ["SOCIOPROFIT_STATE_HOME"] = str(root / "state")
        os.environ["SOCIOPROFIT_RUNTIME_HOME"] = str(root / "run")

        sample = root / "sample.txt"
        sample.write_text("zone publication enqueue smoke\n", encoding="utf-8")

        result = ingest_path(
            file_path=str(sample),
            zone_ref=ZONE_REF,
        )
        plan = plan_publication_request(result["publication_request"])
        record_result = write_publication_record(plan)
        latest = json.loads(Path(record_result["latest_path"]).read_text(encoding="utf-8"))["latest_record"]

        checks = {
            "plan_ok": plan.get("ok") is True,
            "record_ok": record_result.get("ok") is True,
            "record_topic": record_result.get("record", {}).get("topic") == "zone.edge.carrier.ingested.v1",
            "latest_record": latest.get("publication_id") == record_result.get("record", {}).get("publication_id"),
        }
        ok = all(checks.values())
        print(json.dumps({"ok": ok, "checks": checks, "record": record_result.get("record")}, indent=2, sort_keys=True))
        return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
