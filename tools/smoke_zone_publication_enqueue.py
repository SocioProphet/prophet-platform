#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/zone-router/src"))
sys.path.insert(0, str(ROOT / "apps/semantic-bridge/src"))

from zone_router.resolver import resolve_topic  # noqa: E402
from semantic_bridge.validators import validate_zone_publication_record  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        zone_ref = "zone://edge"
        event_type = "carrier.ingested"
        carrier_ref = "carrier://sha256/example"
        event_ref = str(root / "event.json")
        receipt_ref = str(root / "receipt.json")
        catalog_ref = str(root / "catalog.jsonl")

        topic = resolve_topic(zone_ref, event_type)

        record = {
            "version": "0.1",
            "publication_id": str(uuid.uuid4()),
            "created_at": "2026-04-24T00:00:00Z",
            "service_ref": "apps/zone-router",
            "status": "enqueued",
            "zone_ref": zone_ref,
            "event_type": event_type,
            "topic": topic,
            "publication_mode": "resolved",
            "carrier_ref": carrier_ref,
            "event_ref": event_ref,
            "receipt_ref": receipt_ref,
            "catalog_ref": catalog_ref,
        }

        outbox_path = root / "publication_outbox.jsonl"
        with outbox_path.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

        enqueued = json.loads(outbox_path.read_text(encoding="utf-8").splitlines()[0])
        validation = validate_zone_publication_record(enqueued)

        checks = {
            "topic_resolved": topic == "zone.edge.carrier.ingested.v1",
            "record_valid": validation["ok"],
            "outbox_written": outbox_path.exists(),
            "status_enqueued": enqueued.get("status") == "enqueued",
        }
        ok = all(checks.values())
        print(json.dumps({"ok": ok, "checks": checks}, indent=2, sort_keys=True))
        return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
