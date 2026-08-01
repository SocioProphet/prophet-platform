"""Pure, testable core of the telemetry producer adapter.

Wraps an OTLP log record (as emitted by the OTel collector's kafka exporter,
otlp_json encoding) into a CDM EventEnvelope so everything downstream speaks one
contract (Kappa: EventEnvelope is the Map-Log record). No Kafka here.
"""
from __future__ import annotations
import hashlib
from datetime import datetime, timezone


def _stable_id(rec: dict, topic: str) -> str:
    """Deterministic id from content => the producer is replay-idempotent."""
    basis = f"{topic}|{rec.get('timeUnixNano','')}|{rec.get('body','')}|{rec.get('traceId','')}"
    return "ev-" + hashlib.blake2b(basis.encode(), digest_size=16).hexdigest()


def _iso(time_unix_nano) -> str:
    if not time_unix_nano:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return datetime.fromtimestamp(int(time_unix_nano) / 1e9, timezone.utc).isoformat().replace("+00:00", "Z")


def otlp_log_to_envelope(rec: dict, topic: str = "telemetry.logs") -> dict:
    """OTLP log record -> CDM EventEnvelope. `source` from resource service.name;
    body + attributes carried in payload. id/time are deterministic."""
    res = rec.get("resource", {}) or {}
    source = res.get("service.name") or res.get("k8s.pod.name") or "otel"
    return {
        "id": _stable_id(rec, topic),
        "type": "telemetry.log",
        "source": str(source),
        "subject": res.get("k8s.pod.name") or res.get("k8s.namespace.name"),
        "time": _iso(rec.get("timeUnixNano")),
        "topic": topic,
        "payload": {
            "severity": rec.get("severityText"),
            "body": rec.get("body"),
            "attributes": rec.get("attributes", {}),
            "resource": res,
        },
    }
