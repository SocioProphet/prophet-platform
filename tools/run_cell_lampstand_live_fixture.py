#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CELL_SRC = ROOT / "apps/cell-service/src"
LAMPSTAND_SRC = ROOT / "apps/lampstand/src"
FIXTURE_PATH = ROOT / "fixtures/cell/lampstand-live/local-carrier.md"

sys.path.insert(0, str(CELL_SRC))
sys.path.insert(0, str(LAMPSTAND_SRC))

from cell_service import CellService  # noqa: E402
from prophet_platform_lampstand.ingest import ingest_path  # noqa: E402


def fail(message: str) -> None:
    print(f"ERR: {message}", file=sys.stderr)
    raise SystemExit(2)


def main() -> None:
    if not FIXTURE_PATH.exists():
        fail(f"missing live Lampstand fixture file: {FIXTURE_PATH.relative_to(ROOT)}")

    ingest_result = ingest_path(
        file_path=str(FIXTURE_PATH),
        scope_ref="scope://cell/lampstand-live-fixture",
        service_ref="apps/lampstand",
        classifiers=["fixture:cell-lampstand-live", "cell:personal-intelligence"],
        zone_ref="zone://edge",
        topic_ref="/cell/lampstand-live",
    )

    service = CellService()
    cell = {
        "id": "cell://fixture/lampstand-live",
        "owner_ref": "human://fixture-user",
        "kind": "personal",
        "display_name": "Lampstand Live Fixture Cell",
        "policy_ref": "policy://cell/fixture/default",
        "memory_ref": "memory://cell/fixture/default",
        "state": "active",
        "created_at": "2026-05-04T00:00:00Z",
        "updated_at": "2026-05-04T00:00:00Z",
    }
    watch = {
        "id": "watch://fixture/lampstand-live-carrier",
        "cell_id": cell["id"],
        "title": "Lampstand live local carrier",
        "description": "Watch local Lampstand carrier receipts produced from real fixture files.",
        "pattern_refs": ["watch-pattern://fixture/lampstand-live-carrier"],
        "source_scope": [],
        "relevance_policy": "policy://cell/fixture/relevance/lampstand-live",
        "notification_policy": "policy://cell/fixture/notify/private-feed-first",
        "resource_budget": {"max_evaluations_per_hour": 10, "max_notifications_per_day": 2},
        "state": "active",
        "created_at": "2026-05-04T00:00:00Z",
        "updated_at": "2026-05-04T00:00:00Z",
    }
    pattern = {
        "id": "watch-pattern://fixture/lampstand-live-carrier",
        "watch_id": watch["id"],
        "pattern_kind": "typed_template",
        "raw_expression": "Lampstand carrier $carrier_ref ingested",
        "variables": [{"name": "carrier_ref", "type": "custom", "required": True}],
        "version": "0.1.0",
    }

    service.create_cell(cell)
    service.create_watch(watch)
    service.create_watch_pattern(pattern)
    signal = service.ingest_lampstand_result(
        ingest_result,
        cell_id=cell["id"],
        watch_id=watch["id"],
    )

    summary = {
        "ok": True,
        "fixture_path": str(FIXTURE_PATH.relative_to(ROOT)),
        "carrier_ref": ingest_result["carrier_ref"],
        "receipt_path": ingest_result["receipt_path"],
        "payload_path": ingest_result["payload_path"],
        "catalog_path": ingest_result["catalog_path"],
        "signal_id": signal["id"],
        "source_id": signal["source_id"],
        "extractions": signal.get("extractions", {}),
        "evidence_ref_count": len(signal.get("evidence_refs", [])),
        "analytics": service.analytics_snapshot(),
    }

    if summary["evidence_ref_count"] < 5:
        fail("live Lampstand fixture did not preserve expected evidence refs")
    if not summary["extractions"].get("carrier_ref"):
        fail("live Lampstand fixture did not extract carrier_ref")

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
