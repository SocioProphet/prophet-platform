from __future__ import annotations

import json
from pathlib import Path


def enrich_artifact_file(path, *, zone_ref="zone://edge", topic_ref=None):
    artifact_path = Path(path)
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["zone_ref"] = zone_ref
    if topic_ref:
        payload["topic_ref"] = topic_ref
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def enrich_ingest_result(result, *, zone_ref="zone://edge", topic_ref=None):
    out = dict(result)
    for key in ("payload_path", "event_path", "receipt_path"):
        if key in out and out[key]:
            enrich_artifact_file(out[key], zone_ref=zone_ref, topic_ref=topic_ref)
    entry = dict(out.get("entry") or {})
    entry["zone_ref"] = zone_ref
    if topic_ref:
        entry["topic_ref"] = topic_ref
    out["entry"] = entry
    out["zone_ref"] = zone_ref
    if topic_ref:
        out["topic_ref"] = topic_ref
    return out
