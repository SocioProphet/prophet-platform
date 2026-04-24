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
sys.path.insert(0, str(ROOT / "apps/semantic-bridge/src"))

from prophet_platform_lampstand.ingest import ingest_path  # noqa: E402
from zone_router.main import main as zone_router_main  # noqa: E402

ZONE_REF = "zone://edge"


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["SOCIOPROFIT_DATA_HOME"] = str(root / "data")
        os.environ["SOCIOPROFIT_STATE_HOME"] = str(root / "state")
        os.environ["SOCIOPROFIT_RUNTIME_HOME"] = str(root / "run")

        sample = root / "sample.txt"
        sample.write_text("zone router semantic gate smoke\n", encoding="utf-8")

        ingest_result = ingest_path(file_path=str(sample), zone_ref=ZONE_REF)
        request_path = root / "publication_request.json"
        request_path.write_text(json.dumps(ingest_result["publication_request"], indent=2, sort_keys=True) + "\n", encoding="utf-8")

        rc = zone_router_main(["enqueue-request", "--path", str(request_path)])
        if rc != 0:
            return rc

        outbox_latest = Path(os.environ["SOCIOPROFIT_STATE_HOME"]) / "prophet-platform" / "publication-outbox" / "zone-router" / "latest.json"
        latest = json.loads(outbox_latest.read_text(encoding="utf-8"))["latest_record"]
        checks = {
            "latest_status": latest.get("status") == "planned",
            "latest_topic": latest.get("topic") == "zone.edge.carrier.ingested.v1",
            "latest_zone": latest.get("zone_ref") == ZONE_REF,
        }
        ok = all(checks.values())
        print(json.dumps({"ok": ok, "checks": checks, "latest_record": latest}, indent=2, sort_keys=True))
        return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
