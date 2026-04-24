from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

_OUTBOX_VERSION = "1.0"
_SERVICE_REF = "zone-router://v1"


def write_publication_record(plan):
    record = {
        "version": _OUTBOX_VERSION,
        "publication_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "service_ref": _SERVICE_REF,
        "status": "staged",
        "zone_ref": plan.get("zone_ref", ""),
        "event_type": plan.get("event_type", ""),
        "topic": plan.get("topic", ""),
        "publication_mode": plan.get("publication_mode", "resolved"),
        "carrier_ref": plan.get("carrier_ref", ""),
        "event_ref": plan.get("event_ref", ""),
        "receipt_ref": plan.get("receipt_ref", ""),
        "catalog_ref": plan.get("catalog_ref", ""),
    }

    state_home = os.environ.get("SOCIOPROFIT_STATE_HOME", str(Path.home() / ".socioprofit"))
    outbox_dir = Path(state_home) / "zone-router" / "outbox"
    outbox_dir.mkdir(parents=True, exist_ok=True)
    record_path = outbox_dir / f"{record['publication_id']}.json"
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")

    return {"ok": True, "record": record, "staged_path": str(record_path)}
