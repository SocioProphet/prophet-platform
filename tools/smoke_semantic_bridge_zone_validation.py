#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/semantic-bridge/src"))

from semantic_bridge.validators import (  # noqa: E402
    validate_event_envelope,
    validate_membrane_decision,
    validate_zone_publication_plan,
    validate_zone_publication_record,
    validate_zone_publication_request,
)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        event_envelope = {
            "envelope_id": "env-001",
            "created_at": "2026-04-20T00:00:00Z",
            "event_type": "carrier.ingested",
            "producer": "apps/lampstand",
            "subject_ref": "carrier://sha256/example",
            "payload_ref": str(root / "payload.json"),
            "correlation_id": "corr-001",
        }
        membrane = {
            "carrier_id": "carrier://sha256/example",
            "decision": "admit",
            "policy_ref": "policy://edge/default",
            "timestamp": "2026-04-20T00:00:00Z",
        }
        request = {
            "carrier_ref": "carrier://sha256/example",
            "zone_ref": "zone://edge",
            "event_ref": str(root / "event.json"),
            "receipt_ref": str(root / "receipt.json"),
            "catalog_ref": str(root / "catalog.jsonl"),
        }
        plan = {
            "ok": True,
            "version": "0.1",
            "zone_ref": "zone://edge",
            "event_type": "carrier.ingested",
            "topic": "zone.edge.carrier.ingested.v1",
            "publication_mode": "resolved",
            "carrier_ref": "carrier://sha256/example",
            "event_ref": request["event_ref"],
            "receipt_ref": request["receipt_ref"],
            "catalog_ref": request["catalog_ref"],
        }
        record = {
            "version": "0.1",
            "publication_id": "pub-001",
            "created_at": "2026-04-20T00:00:00Z",
            "service_ref": "apps/zone-router",
            "status": "planned",
            "zone_ref": "zone://edge",
            "event_type": "carrier.ingested",
            "topic": "zone.edge.carrier.ingested.v1",
            "publication_mode": "resolved",
            "carrier_ref": "carrier://sha256/example",
            "event_ref": request["event_ref"],
            "receipt_ref": request["receipt_ref"],
            "catalog_ref": request["catalog_ref"],
        }

        checks = {
            "event_envelope": validate_event_envelope(event_envelope)["ok"],
            "membrane": validate_membrane_decision(membrane)["ok"],
            "zone_publication_request": validate_zone_publication_request(request)["ok"],
            "zone_publication_plan": validate_zone_publication_plan(plan)["ok"],
            "zone_publication_record": validate_zone_publication_record(record)["ok"],
        }
        ok = all(checks.values())
        print(json.dumps({"ok": ok, "checks": checks}, indent=2, sort_keys=True))
        return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
