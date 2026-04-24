#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/zone-router/src"))
sys.path.insert(0, str(ROOT / "apps/semantic-bridge/src"))

from zone_router.resolver import resolve_topic  # noqa: E402
from semantic_bridge.validators import validate_zone_publication_plan  # noqa: E402


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

        plan = {
            "ok": True,
            "version": "0.1",
            "zone_ref": zone_ref,
            "event_type": event_type,
            "topic": topic,
            "publication_mode": "resolved",
            "carrier_ref": carrier_ref,
            "event_ref": event_ref,
            "receipt_ref": receipt_ref,
            "catalog_ref": catalog_ref,
        }

        validation = validate_zone_publication_plan(plan)

        checks = {
            "topic_resolved": topic == "zone.edge.carrier.ingested.v1",
            "plan_valid": validation["ok"],
        }
        ok = all(checks.values())
        print(json.dumps({"ok": ok, "checks": checks, "plan": plan}, indent=2, sort_keys=True))
        return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
