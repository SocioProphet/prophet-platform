from __future__ import annotations


def resolve_topic(zone_ref, event_type):
    zone = str(zone_ref or "edge").replace("zone://", "").strip("/") or "edge"
    normalized = str(event_type or "unknown").replace("/", ".").replace("_", ".")
    return f"zone.{zone}.{normalized}.v1"
